# csft
Get instagram follower counts and store them in a Google Sheets sheet

## Setup
1. `pip install --user -r requirements.txt`
2. Fill in and change required values in `config.toml` (nearly non-existing error handling so make sure everything is set correctly)
3. [Authorize pygsheets](https://pygsheets.readthedocs.io/en/stable/authorization.html)
    1. Generate required `client_secret.json` file and place it alongside the script.
    2. Complete the authorization flow on first run.

## Behaviour and configuration variables
### Base section
First time the script is run (provided that it is configured properly) it populates `insta_uid_col`, `followers_col` and `timestamp_col` with user ID, follower count and timestamp for each account from `instagram_col`, respectively. Every subsequent time `update()` is run (every time the script is run and, if `recheck_periodically` is enabled, every `minutes_interval`), if timestamp is older than 1 day, follower count is rechecked and timestamp updated. If there are any new handles in `instagram_col` when `update()` executes again they are being treated as handles with timestamps older than 1 day and their follower counts are updated and their user IDs are filled in too.
* `sheet_name` - Name of sheet in which data and archive worksheets are located.
* `worksheet_name` - Name of the worksheet in which instagram handles, current follower counts and timestamps are stored.
* `instagram_col` - Column number in data worksheet in which instagram handles are stored.
* `insta_uid_col` - Column number in data worksheet in which instagram user IDs are stored. Used if, for example, user changes their handle
* `followers_col` - Column number in data worksheet in which current follower counts are stored.
* `timestamp_col` - Column number in data worksheet in which timestamps of last follower count update are stored.
* `recheck_periodically` - Whether the script should keep running and check for updates every `minutes_interval` minutes instead of exiting after checking for updates once and trying to store current data to archive worksheet.
* `minutes_interval` - See above.
### Archive section
Every day at 23:30 (if `archive` is set to `True`) the script copies follower counts from data worksheet to archive worksheet, to a column with today's date as a header.
* `archive` - See above.
* `archive_name` - Name of the worksheet to which data is archived each day.
    * On the first run of `storeOldData()` function first column is populated with instagram handles from data worksheet, then second column is populated with a header (today's date) and follower counts from data worksheet
* `force_update` - Whether the script should overwrite today's data (if already stored in archive worksheet) each time `storeOldData()` is run.
