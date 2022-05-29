import os
import math
from tda import auth, client
import httpx
import datetime as dt
from dotenv import load_dotenv
import chromedriver_autoinstaller

load_dotenv()
chromedriver_autoinstaller.install()

######################
### Trade Settings ###
######################
symbol = os.getenv('SYMBOL')
target_dte = int(os.getenv('TARGET_DTE'))
trade_type = os.getenv('TRADE_TYPE')
otm_price_target = float(os.getenv('OTM_PRICE_TARGET'))
spread_price_target = float(os.getenv('SPREAD_PRICE_TARGET'))
spread_width_target = float(os.getenv('SPREAD_WIDTH_TARGET'))

#####################
### TDA FUNCTIONS ###
#####################
def get_quote(symbol, c):
    q = c.get_quote(symbol)
    assert q.status_code == httpx.codes.OK, q.raise_for_status()
    return q.json()

def get_expiration(expDateMap: dict):
    distance = math.inf
    closest_exp = None

    for expiration, details in expDateMap.items():
        split_exp = expiration.split(":", 1)
        exp = dt.datetime.strptime(split_exp[0], "%Y-%m-%d")
        dte = int(split_exp[1])
        delta = abs(target_dte - dte)
    
        if delta < distance:
            closest_exp = details

    return closest_exp

def get_option_chain(c: client.Client):
    r = c.get_option_chain(symbol=symbol, strike_range=client.Client.Options.StrikeRange.OUT_OF_THE_MONEY, option_type=client.Client.Options.Type.STANDARD, from_date=dt.datetime.now() + dt.timedelta(days=target_dte-10), to_date=dt.datetime.now() + dt.timedelta(days=target_dte+10)  )
    assert r.status_code == httpx.codes.OK, r.raise_for_status()
    return r.json()

def create_client():
    token_path = 'token.json'
    api_key = f"{os.getenv('API_KEY')}@AMER.OAUTHAP"
    redirect_uri = os.getenv('REDIRECT_URI')

    try:
        c = auth.client_from_token_file(token_path, api_key)
    except FileNotFoundError:
        from selenium import webdriver
        with webdriver.Chrome() as driver:
            c = auth.client_from_login_flow(
            driver, api_key, redirect_uri, token_path)
                
    return c

########################
### STRIKE FUNCTIONS ###
########################
def get_otm_strike(closest_exp: dict):
    distance = math.inf
    otm_put = None
    for details in closest_exp.values():
        short = next((type for type in details if type['settlementType'] == 'P'), None)
    
        if short is None:
            continue

        price = (short['bid']+short['ask'])/2
        delta = abs(otm_price_target - price)
        if delta < distance:
            distance = delta
            otm_put = short
    return otm_put

def get_spread_strikes(spread_price_target, spread_width_target, closest_exp):
    distance = math.inf
    best_short = None
    best_long = None
    price_width = 0.0
    for short_strike, short_details in closest_exp.items():
        short_strike = float(short_strike)
        long_strike = str(short_strike + spread_width_target)

        long_details = closest_exp.get(long_strike)

        if long_details is None:
            continue

        short = next((type for type in short_details if type['settlementType'] == 'P'), None)
        long = next((type for type in long_details if type['settlementType'] == 'P'), None)

        if short is None or long is None:
            continue

        price_width = long['ask']-short['bid']
        delta = abs(spread_price_target - price_width)

        if delta < distance:
            distance = delta
            best_price = price_width
            best_short = short
            best_long = long
    return best_short,best_long,best_price

# Setup Client
c = create_client()

# Get the Option Chain
option_chain = get_option_chain(c)

if trade_type == "1.1.2":
    expDateMap = option_chain['putExpDateMap']

# Get Closest Expiration
expiry = get_expiration(expDateMap)

# Find OTM Strike
otm_put = get_otm_strike(expiry)

# Find Spread
best_short, best_long, best_price = get_spread_strikes(spread_price_target, spread_width_target, expiry)

# Get Current Price
ticker = get_quote(symbol, c)

# Print Results
print(f"2x {otm_put['description']}")
print(f"1x {best_short['description']}")
print(f"1x {best_long['description']}")
print(f"Short Premium: 2x ${otm_put['bid']}")
print(f"Spread Premium: 1x ${best_price}")
print(f"Total Premium: ${2*float(otm_put['bid']) - float(best_price)}")
print(f"Downside Protection: {1-(otm_put['strikePrice']/ticker[symbol]['lastPrice'])}%")