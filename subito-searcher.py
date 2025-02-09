import argparse
import time as t
from datetime import datetime, time

from services.queries import QueryManager
from services.telegram import TelegramService
from utils import in_between

parser = argparse.ArgumentParser()
parser.add_argument("--add", dest='name', help="name of new tracking to be added")
parser.add_argument("--url", help="url for your new tracking's search query")
parser.add_argument("--minPrice", help="minimum price for the query")
parser.add_argument("--maxPrice", help="maximum price for the query")
parser.add_argument("--delete", help="name of the search you want to delete")
parser.add_argument('--refresh', '-r', dest='refresh', action='store_true', help="refresh search results once")
parser.set_defaults(refresh=False)
parser.add_argument('--daemon', '-d', dest='daemon', action='store_true',
                    help="keep refreshing search results forever (default delay 120 seconds)")
parser.set_defaults(daemon=False)
parser.add_argument('--activeHour', '-ah', dest='activeHour', help="Time slot. Hour when to be active in 24h notation")
parser.add_argument('--pauseHour', '-ph', dest='pauseHour', help="Time slot. Hour when to pause in 24h notation")
parser.add_argument('--delay', dest='delay', help="delay for the daemon option (in seconds)")
parser.set_defaults(delay=120)
parser.add_argument('--list', dest='list', action='store_true', help="print a list of current trackings")
parser.set_defaults(list=False)
parser.add_argument('--short_list', dest='short_list', action='store_true', help="print a more compact list")
parser.set_defaults(short_list=False)
parser.add_argument('--tgoff', dest='tgoff', action='store_true', help="turn off telegram messages")
parser.set_defaults(tgoff=False)
parser.add_argument('--notifyoff', dest='win_notifyoff', action='store_true', help="turn off windows notifications")
parser.set_defaults(win_notifyoff=False)
parser.add_argument('--addtoken', dest='token', help="telegram setup: add bot API token")
parser.add_argument('--addchatid', dest='chatid', help="telegram setup: add bot chat id")

args = parser.parse_args()

if __name__ == '__main__':
    telegram = TelegramService(args.tgoff)
    telegram.load_api_credentials()

    query_manager = QueryManager(telegram)
    query_manager.load_queries()

    if args.list:
        print(datetime.now().strftime("%Y-%m-%d, %H:%M:%S") + " printing current status...")
        query_manager.print_queries()

    if args.short_list:
        print(datetime.now().strftime("%Y-%m-%d, %H:%M:%S") + " printing quick sitrep...")
        query_manager.print_sitrep()

    if args.url is not None and args.name is not None:
        query_manager.add(args.url, args.name, args.minPrice if args.minPrice is not None else "null",
                          args.maxPrice if args.maxPrice is not None else "null")
        query_manager.run_query(args.url, args.name, False, args.minPrice if args.minPrice is not None else "null",
                                args.maxPrice if args.maxPrice is not None else "null", )
        print(datetime.now().strftime("%Y-%m-%d, %H:%M:%S") + " Query added.")

    if args.delete is not None:
        query_manager.delete(args.delete)

    if args.activeHour is None:
        args.activeHour = "0"

    if args.pauseHour is None:
        args.pauseHour = "0"

    if args.token is not None and args.chatid is not None:
        apiCredentials = {
            "token": args.token,
            "chatid": args.chatid
        }
        telegram.save_api_credentials(apiCredentials)

    if args.refresh:
        query_manager.refresh(True)

    print()
    query_manager.save_queries()

    if args.daemon:
        notify = False  # Don't flood with notifications the first time
        while True:
            if in_between(datetime.now().time(), time(int(args.activeHour)), time(int(args.pauseHour))):
                query_manager.refresh(notify)
                notify = True
                print()
                print(str(args.delay) + " seconds to next poll.")
                query_manager.save_queries()
            t.sleep(int(args.delay))
