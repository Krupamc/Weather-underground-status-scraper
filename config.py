# Config for the Status checker

consecutive_offline = 3
pytz_timezone = "US/Eastern"

#---Offline Emails---
d_subject = "[OFFLINE] {station['name']} ({station_id}) appears offline"
d_body = {
    "Station {station_name} ({station_id}) appears OFFLINE on Weather Underground.\n"
    "URL: {url}\n"
    "Checked at: {now}\n"
    "Consecutive offline checks: {consecutive_offline}\n"

}

# Email Setup
server = "smtp.gmail.com"
port = 587
username = "theunknownboss1999@gmail.com"
password = "dpdlzimvidrstktv"
from_email = "Save Barnegat Bay Mesonet Notifications <theunknownboss1999@gmail.com>"


# Email Addresses
#global_recipients = ["krupampatel710@gmail.com", "outreach@savebarnegatbay.org"]
global_recipients = ["krupampatel710@gmail.com"]

recipients = {
    #"KNJBERKE13": "",
    #"KNJWARET3": "",
    #"KNJMANAH111": "",
    "KNJMANAH7": "fixmytechnj@gmail.com",
    #"KNJBAYHE18": "",
    #"KNJLONGB89": "",
    #"KNJLONGB21": "",
    #"KNJBEACH64": "",
    #"KNJOCEAN178": "",
    #"KNJSEASI44": "",
    #"Ecocenter": ""
}

stations = {
    "KNJBERKE13": "Island Beach State Park Bathhouse #1",
    "KNJWARET3": "Sedge Island",
    "KNJMANAH111": "Stafford Municipal Complex",
    "KNJMANAH7": "MATES/Stafford",
    "KNJBAYHE18": "Bayhead Fire Company #1",
    "KNJLONGB89": "LBT Marine Field Station",
    "KNJLONGB21": "LBI Foundation",
    "KNJBEACH64": "Beachwood Yacht Club",
    "KNJOCEAN178": "Ocean Gate Yacht Club",
    "KNJSEASI44": "Seaside Park Yacht Club",
    "Ecocenter": "Ecocenter",
}
