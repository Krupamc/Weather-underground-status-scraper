# Sends Email Alerts
import os, sys, smtplib, ssl, requests
from email.message import EmailMessage

# Get Config
api_base = os.getenv("API_BASE", "http://web:8000")
scraper_api_key = os.getenv("SCRAPER_API_KEY", "")
smtp_host = os.getenv("SERVER", "")
smtp_port = int(os.getenv("PORT", "587"))
smtp_username = os.getenv("USERNAME", "")
smtp_password = os.getenv("PASSWORD", "")
smtp_from_email = os.getenv("FROM_EMAIL", "")

# Get all admin/global emails
def get_recipients(email_type: str):
    if email_type == "admin":
        url=f"{api_base}/scraper/recipients"
    elif email_type == "weather":
        url=f"{api_base}/scraper/weather/recipients"

    r = requests.get(url, headers={"x-api-key": scraper_api_key}, timeout=15)
    r.raise_for_status()

    print(" I think we'regonna makeaslightadjustmentI need to makesogar,I'm getting foodalittle bit more consistently now, andI want to beable to preserveitincaseI needitlonger,so we'regonna this is not the correctitemcaptured forus to justignore that's what we cando thatall right differenton theslides foralotlonger than justregular too.<en-US> The bear would justkillme right now there wasnowayI couldfightnoshe bearI toolowenergyI'm too weakI can'trunit fullspeed the thing would justripme toshredsmy bestchance to survive out here right now is justavoiding bears atallcosts and being veryaware ofmy surroundings.<en-US>I've notencaps did somestuff with somevoyers, right?<en-US>It'sonaberry verybelly tellmeeverything verybelly untilfinallyIenough help to makeasprayhide and ifI getafew more of thesesquarehidesI can eventually make thatpumpa verynicestyleon theworld twenty sevenIwake upafeeling thatdoes notsobraveinrealizeremember whenI was consideringearlierIfeel like right nowinreallifeIfeel likeI gotmyneck is likeallsortIfeel likeI'm gettingafever andmyskin isall tingly andmystomach is justkind of turning over andit reallydoesfeel likearawsquirrelinreallife anywaysside of thisfishside of thisfish isrunningonI was forced tosnasharockstairs anyways likeI was saying theslower paceI deliberately decided to makea videoalittle bitslower becauseI don't knowI don't want to beable tohold there'sa ironall over thisanswer hereI didn'tratherpicka minuteIguessit was cross this was good this wasa good thing right hereflupa goodrock yourrollrock deep deepinstinct deep withinmegonnado something thatIlove thatmaximummeans youmayroll over those differentberries big finesareway moreinactiveImight actually getfishing cattleI want to talk aboutdoing any uhchannel cleaned up hereside of thefishside of this thing rightI clean thefish andso we gotafish smoking now preserveit too,mysfocus needs to beon buildingacase,a food cash.<en-US> This wouldallowme toautomaticin them up tophysicallyeat food anymorein thebar and then thegame willalldrop toadoptionor food for you and make sure they'rein the correctdayoneveryrich.<en-US> Theonlyleft you somewhat protectits carder even due to the cheston theground you can haveit also verifyonasnatchinto that chest andstealing byputtingitina foodcache makes that less likely tohappen, butIwentit would and hereit wasbasicallyI canputmy foodinto here andI canchoosemyrationallevel and thenI'll justautoeat from thissoI don't actually need to carry yourown foodit will justautomatically get consumed whichI thinkit'sfun didI justdo what didI justdo thatwhy didI justgopick up andmushroom without thinking thatorwhy didIdo thatI thoughtI couldeat thosemushroomsbrownmushroomsaware thatIdo thatadrive to bikelater?<en-US> The foodcharge is good be thekey food safeorImeanit'swheremy food will beeaten out of the problem though is predators theyaregoing to want this foodsoI have tofind somewhereI couldputit that isn'tgoing to getme toshruggle andI thinkI'mstill justgoing toputit upina treegonnago to thislittle likehear what they're called they're like looking thingswhere you canput your foodin themI dida survivalcoarse thingin thearticle and one of the people whowon theshowalone wewent to hissitewherehe actuallywon theshow and hislittle food cashwherehe cutdownstatus:", r.status_code)

    recipients = r.json()

    
    # Only admin emails
    if email_type == "admin":
        return [
            recipient["email"]
            for recipient in recipients
            if recipient["recipient_type"] == "admin"
        ]

    elif email_type == "weather":
        return recipients

# Send email
def send_email(subject: str, body: str, recipients: list[str]):
    if not recipients:
        print("[ALERT ERROR]: No admin recipients configured")
        return 1

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_from_email
    msg["Bcc"] = ", ".join(recipients)
    msg.set_content(body)

    context = ssl.create_default_context()

    # Send Email
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls(context=context)
        server.login(smtp_username, smtp_password)
        server.send_message(msg)

    return 0

# Get Arguments from terminal:
if len(sys.argv) < 3:
    print("[ERROR]: Arguments Missing.")
    print('"SUBJECT" "BODY"')
    sys.exit(1)

# Set Variables
email_type = sys.argv[1]
subject = sys.argv[2]
body = sys.argv[3]

recipients = get_recipients(email_type)

# Send Email
send_email(subject=subject, body=body, recipients=recipients)