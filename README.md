# Facebook Vcard Exporter

If you want freedom to manage your contacts in a tool of your choosing rather than leaving it to Zuck.

## Disclaimer
When using this tool, Facebook can see that you're using an automated tool, which violates their terms. There is a risk that Facebook may decide to put a temporary or permanent ban on your account (though I haven't heard of this happening to anyone yet). I am not responsible for this or any other outcomes that may occur as a result of the use of this software.

## What this is
This tool will only extract the data that your friends have already explicitly made it available to you. If the amount or content of the data freaks you (like it did to me!), then it's a good reminder for us all to check our profiles/privacy settings to make sure that we only share what we want others to be able to see.

It works like this:
1. Open your friends list page (on m.facebook.com) and save to `db/friend_list.html`
2. Download your friend's profiles (on mbasic.facebook.com) to `db/profiles/`
3. Parse profile files and adds that data to the database.
4. Exports the profile data as Vcard files to `db/vcards`

All data is saved locally in `db/data.db` as a sqlite database.
 
## Usage
Prerequisites:
- Make sure that `python 3`, `pip` and `venv` are installed.

### Preparation:
1. Clone this repository
2. `cd` into the cloned folder 
4. Run `python3 -m venv venv/` to activate the virtual environment. This is optional if you already have the required packages installed in your environment.
5. Run `pip install -r requirements.txt` to install the project’s dependencies inside the active virtual environment.

### Usage
1. Run `python main.py`. On the first run, it'll ask for your Facebook username/password and Mapbox API Key. It saves these to the local `.env` file for use in subsequent runs (eg if you add more friends).
2. The tool will then index your friend list, download friend's profiles, geocode coordinates, and create the map. You can optionally use any of these flags to perform only certain actions:

- `--list` Sign in, download friends list HTML
- `--index` Extract friend list HTML to database
- `--download` Download profile for each friend in index 
- `--parse` Extract profiles HTML to database
- `--vcard` Exports the profile data in the database to Vcard files
- `--json` Export sqlite database to JSON files (db/json/)

If something breaks, just run the script again. It's built to pick up where it left off at all stages.
Please file an issue if you run into any problems. Enjoy!