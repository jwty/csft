from datetime import date, datetime, timedelta
import instaloader
import pygsheets
import logging
import schedule
import time
import toml


## SETTINGS
__version__ = '1.3 "low speed high drag"'
config = toml.load('config.toml')
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
def openSheet():
    try:
        sheet = sheetsClient.open(sheet_name)
    except pygsheets.exceptions.SpreadsheetNotFound:
        logging.critical('Sheet "{}" not found - check config!'.format(sheet_name))
        raise SystemExit(0)
    return sheet
def openDataSheet():
    sheet = openSheet()
    try:
        dataWorksheet = sheet.worksheet_by_title(worksheet_name)
    except pygsheets.exceptions.WorksheetNotFound:
        logging.critical('Worksheet "{}" not found - check config!'.format(worksheet_name))
        raise SystemExit(0)
    return dataWorksheet


## STORE OLD FOLLOWERS DATA
def storeOldData():
    sheet = openSheet()
    try:
        archiveWorksheet = sheet.worksheet_by_title(archive_name)
    except pygsheets.exceptions.WorksheetNotFound:
        logging.critical('Archive worksheet "{}" not found - not archiving!'.format(archive_name))
        return -1
    dataWorksheet = openDataSheet()
    instaHandles = dataWorksheet.get_col(instagram_col, include_tailing_empty=False)[1:]
    today = date.today().strftime('%d-%m-%Y')
    followerCounts = dataWorksheet.get_col(followers_col, include_tailing_empty=False)[1:]
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


## UPDATE FOLLOWERS COUNTS
def updateFollowersCounts():
    logging.info('Updating followers count.')
    dataWorksheet = openDataSheet()
    instaHandles = dataWorksheet.get_col(instagram_col, returnas='cell', include_tailing_empty=False)
    instaHandles = instaHandles[1:] # strip column header
    timestamps = dataWorksheet.get_col(timestamp_col)[1:] # too much read requests fix
    for i, handle in enumerate(instaHandles):
        if not handle.value_unformatted == handle.value_unformatted.strip():
            handle.set_value(handle.value_unformatted.strip()) # yolostrip unnecessary whitespaces
            logging.warning('Stripped whitespaces from "{}" - check sheet!'.format(handle.value_unformatted))
        currentTimestamp = timestamps[i]
        try:
            currentTimestamp = datetime.strptime(currentTimestamp, '%d-%m-%Y %H:%M:%S') # convert to datetime object
        except ValueError:
            currentTimestamp = datetime.min
        if currentTimestamp + timedelta(days=1) > datetime.now():
            logging.debug('Skipping {}'.format(handle.value_unformatted))
            continue
        try:
            profile = instaloader.Profile.from_username(loader.context, handle.value_unformatted)
        except instaloader.exceptions.ProfileNotExistsException:
            logging.warning(r'Profile "{}" does not exist.'.format(handle.value_unformatted))
            handle.neighbour((0,followers_col - instagram_col)).set_value('ERR: does not exist')
            continue
        dataWorksheet.update_row(handle.row, [profile.followers, datetime.now().strftime('%d-%m-%Y %H:%M:%S')], followers_col - 1)
        logging.info('Updating {}, followers: {}'.format(handle.value_unformatted, profile.followers))
    logging.info('Finished.')


## RUN ONCE BEFORE SCHEDULE LOOP STARTS
updateFollowersCounts()
storeOldData()


## SCHEDULE LOOP
if recheck_periodically:
    logging.info('Checking for updates every {} minutes. Zzz...'.format(minutes_interval))
    schedule.every(minutes_interval).minutes.do(updateFollowersCounts)
    schedule.every().day.at('23:30').do(storeOldData)
    while True:
        time.sleep(minutes_interval * 30)
        logging.debug('Checking for pending jobs.')
        schedule.run_pending()
else:
    logging.info('recheck_periodically set to false, exiting.')
