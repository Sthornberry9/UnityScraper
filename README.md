Usage: python main.py
enter TitleIDs separated by comma. Currently the script can't fit the entire JSON.text I have in the repository, but it contains a list of every titleID XboxUnity lists.

Script will notify of an error if you search for titleids that don't have covers or titleupdates, but will still download what's available for TitleID if missing one or the other.
All JSON responses from Unity are saved in the respective TitleID folder for records, and update versions are stored separately by MediaID.

Todo: Rate-Limiting
      Fix/cleanup GUI
      Make save location configureable.

      Anyone wanting a copy of the full scrape, please don't hammer Unity's servers. DM me on discord @trapemall for a download instead. I plan on packaging it into an archive since this not being available anywhere was the inspiration for the script.
