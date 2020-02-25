from datetime import date, datetime, timedelta
import instaloader
import pygsheets
import logging
import schedule
import time
import toml


## SETTINGS
__version__ = '2.1 "low speed high drag"'
config = toml.load('config-dev.toml')
for key, value in config['base'].items():
    globals()[key] = value
for key, value in config['archive'].items():
    globals()[key] = value


## SETUP LOGGING
logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.FileHandler('csft.log', mode='a'), logging.StreamHandler()])
logging.getLogger("googleapiclient.discovery").setLevel(logging.WARNING)
logging.info('--- csft.py {} ---'.format(__version__))


## GOOGLE AUTHORIZATION
try:
    sheetsClient = pygsheets.authorize()
except:
    logging.critical('Unable to authorize with Google API!')
    raise SystemExit(0)


## INSTALOADER INSTANCE
loader = instaloader.Instaloader()


## OPEN SHEETS
try:
    sheet = sheetsClient.open(sheet_name)
except pygsheets.exceptions.SpreadsheetNotFound:
    logging.critical('Sheet "{}" not found - check config!'.format(sheet_name))
    raise SystemExit(0)
try:
    dataWorksheet = sheet.worksheet_by_title(worksheet_name)
except pygsheets.exceptions.WorksheetNotFound:
    logging.critical('Worksheet "{}" not found - check config!'.format(worksheet_name))
    raise SystemExit(0)


## UPDATE FOLLOWER COUNTS AND UIDS
def updateFollowerCount(handleCell, followers):
    logging.info('Updating {}, followers: {}'.format(handleCell.value_unformatted, followers))
    dataWorksheet.update_row(handleCell.row, [followers, datetime.now().strftime('%d-%m-%Y %H:%M:%S')], followers_col - 1)

def getHandleByUID(handleCell, UID):
    try:
        profileHandle = instaloader.Profile.from_id(loader.context, UID).username
    except instaloader.exceptions.ProfileNotExistsException:
        return False
    return profileHandle

def update():
    logging.info('Starting update.')
    instaHandleCells = dataWorksheet.get_col(instagram_col, returnas='cell', include_tailing_empty=False)[1:]
    UIDCells = dataWorksheet.get_col(insta_uid_col, returnas='cell')[1:]
    timestamps = dataWorksheet.get_col(timestamp_col)[1:]
    for i, handle in enumerate(instaHandleCells):
        try:
            currentTimestamp = datetime.strptime(timestamps[i], '%d-%m-%Y %H:%M:%S')
        except ValueError:
            currentTimestamp = datetime.min
        if currentTimestamp + timedelta(days=1) > datetime.now():
            continue
        if not handle.value_unformatted == handle.value_unformatted.strip():
            handle.set_value(handle.value_unformatted.strip()) # yolostrip unnecessary whitespaces
            logging.warning('Stripped whitespaces from "{}" - check sheet!'.format(handle.value_unformatted))
        try:
            profile = instaloader.Profile.from_username(loader.context, handle.value_unformatted)
        except instaloader.exceptions.ProfileNotExistsException:
            if str(UIDCells[i].value_unformatted).isnumeric():
                logging.warning('Profile "{}" does not exist! Checking via UID.'.format(handle.value_unformatted))
            else:
                logging.warning('Profile "{}" does not exist and UID is invalid - skipping.'.format(handle.value_unformatted))
                continue
            newHandle = getHandleByUID(handle, UIDCells[i].value_unformatted)
            if newHandle:
                logging.info('New handle found, updating sheet with "{}".'.format(newHandle))
                handle.set_value(newHandle)
            else:
                logging.warning('Profile ID "{}" does not exist - skipping.'.format(UIDCells[i].value_unformatted))
                continue
        updateFollowerCount(handle, profile.followers)
        if not UIDCells[i].value_unformatted:
            logging.info('Updating UID for handle "{}".'.format(handle.value_unformatted))
            UIDCells[i].set_value(profile.userid)
    logging.info('Finished.')


## STORE OLD FOLLOWERS DATA
def storeOldData():
    try:
        archiveWorksheet = sheet.worksheet_by_title(archive_name)
    except pygsheets.exceptions.WorksheetNotFound:
        logging.critical('Archive worksheet "{}" not found - not archiving!'.format(archive_name))
        return -1
    logging.info('Storing old data to archive sheet.')
    instaHandles = dataWorksheet.get_col(instagram_col, include_tailing_empty=False)[1:]
    followerCounts = dataWorksheet.get_col(followers_col, include_tailing_empty=False)[1:]
    today = date.today().strftime('%d-%m-%Y')
    for i, row in enumerate(followerCounts):
        followerCounts[i] = row.replace(',','') # because get_col() gets formatted values
        if not followerCounts[i].isnumeric():
            followerCounts[i] = '' # remove garbage data
    followersColumn = [today] + followerCounts
    logging.info('Storing followers data as for {}'.format(today))
    archiveWorksheet.update_col(1, instaHandles, row_offset=1)
    columnHeaders = archiveWorksheet.get_row(1, include_tailing_empty=False)
    currentArchiveColIndex = len(columnHeaders) + 1 if columnHeaders else 2
    if columnHeaders and columnHeaders[-1] == today:
        if force_update == False:
            logging.info('Data for {} already present, skipping.'.format(today))
            return 1
        else:
            logging.warning('"force_update" enabled - overwriting stored data!')
            currentArchiveColIndex =  len(columnHeaders)
    archiveWorksheet.update_col(currentArchiveColIndex, followersColumn)
    logging.info('Finished')


## RUN ONCE BEFORE SCHEDULE LOOP STARTS
update()
if archive:
    storeOldData()


## SCHEDULE LOOP
if recheck_periodically:
    logging.info('Checking for updates every {} minutes. Zzz...'.format(minutes_interval))
    schedule.every(minutes_interval).minutes.do(update)
    if archive:
        schedule.every().day.at('23:30').do(storeOldData)
    while True:
        time.sleep(minutes_interval * 30)
        logging.debug('Checking for pending jobs.')
        schedule.run_pending()
else:
    logging.info('recheck_periodically set to false, exiting.')
