# Public APIs Reference

A curated reference of free/public APIs, sourced from the community
[`public-apis/public-apis`](https://github.com/public-apis/public-apis) project
(a README catalog of ~1,400+ APIs — there is no package to "install"; these are
just HTTP endpoints you call directly).

This file captures the categories most relevant to a **GDP / economic data
dashboard**: Finance, Currency Exchange, Cryptocurrency, Government, Open Data,
and Environment. For the full catalog (Animals, Weather, Games, Geocoding, etc.),
see the upstream repo.

> **Auth** = what credentials a request needs (`No` = no key required).
> **HTTPS** = endpoint served over TLS. **CORS** = browser cross-origin support.

---

## ⭐ Most relevant for this GDP dashboard

This app currently reads GDP from a static [World Bank Open Data](https://data.worldbank.org/)
CSV (`data/gdp_data.csv`). These no-key / low-friction macroeconomic sources are
the natural candidates if you want to pull data live instead:

| API | Why it fits | Auth | URL |
|:---|:---|:---|:---|
| World Bank Open Data | Same source as the bundled CSV; GDP, population, indicators by country/year | No | https://datahelpdesk.worldbank.org/knowledgebase/articles/889392 |
| FRED (St. Louis Fed) | US & global macro time series (GDP, CPI, rates) | apiKey | https://fred.stlouisfed.org/docs/api/fred/ |
| Econdb | Global macroeconomic data | No | https://www.econdb.com/api/ |
| Fed Treasury (Fiscal Data) | U.S. Treasury fiscal datasets | No | https://fiscaldata.treasury.gov/api-documentation/ |
| Frankfurter | FX rates / currency conversion / time series (no key) | No | https://www.frankfurter.app/docs |
| SEC EDGAR | Annual reports / financials of public US companies | No | https://www.sec.gov/edgar/sec-api-documentation |

> Note: World Bank is not in the upstream "Government/Open Data" tables but is
> the canonical free source for this dashboard's data, so it is listed here.

---

## Finance

| API | Description | Auth | HTTPS | CORS | URL |
|:---|:---|:---|:---|:---|:---|
| Marketstack | Real-Time, Intraday & Historical Market Data | apiKey | Yes | Unknown | https://marketstack.com |
| Aletheia | Insider trading data, earnings call analysis, financial statements | apiKey | Yes | Yes | https://aletheiaapi.com/ |
| Alpaca | Realtime and historical market data on US equities and ETFs | apiKey | Yes | Yes | https://alpaca.markets/docs/api-documentation/api-v2/market-data/alpaca-data-api-v2/ |
| Alpha Vantage | Realtime and historical stock data | apiKey | Yes | Unknown | https://www.alphavantage.co/ |
| Banco do Brasil | Banco do Brasil financial transaction APIs | OAuth | Yes | Yes | https://developers.bb.com.br/home |
| Bank Data API | Instant IBAN and SWIFT number validation | apiKey | Yes | Unknown | https://apilayer.com/marketplace/bank_data-api |
| Billplz | Payment platform | apiKey | Yes | Unknown | https://www.billplz.com/api |
| Binlist | Database of IIN/BIN information | No | Yes | Unknown | https://binlist.net/ |
| Boleto.Cloud | Generate boletos in Brazil | apiKey | Yes | Unknown | https://boleto.cloud/ |
| Citi | Citigroup account and statement data APIs | apiKey | Yes | Unknown | https://sandbox.developerhub.citi.com/api-catalog-list |
| Econdb | Global macroeconomic data | No | Yes | Yes | https://www.econdb.com/api/ |
| EconPulse | Live economic data — CPI, PPI, energy, treasury rates, BTC premium | apiKey | Yes | Yes | https://econpulse.io |
| Fed Treasury | U.S. Department of the Treasury Data | No | Yes | Unknown | https://fiscaldata.treasury.gov/api-documentation/ |
| Finage | Stock, currency, crypto, indices, ETF data | apiKey | Yes | Unknown | https://finage.co.uk |
| Financial Modeling Prep | Realtime and historical stock data | apiKey | Yes | Unknown | https://site.financialmodelingprep.com/developer/docs |
| Finnhub | Real-Time RESTful APIs for Stocks, Currencies, Crypto | apiKey | Yes | Unknown | https://finnhub.io/docs/api |
| FRED | Economic data from the Federal Reserve Bank of St. Louis | apiKey | Yes | Yes | https://fred.stlouisfed.org/docs/api/fred/ |
| Front Accounting | Multilingual/multicurrency small-business software | OAuth | Yes | Yes | https://frontaccounting.com/fawiki/index.php?n=Devel.SimpleAPIModule |
| Helium | News bias scoring, balanced news, live market data | No | Yes | Yes | https://heliumtrades.com/mcp-page/ |
| Hotstoks | Stock market data powered by SQL | apiKey | Yes | Yes | https://hotstoks.com |
| IBANforge | IBAN validation and BIC/SWIFT lookup, 75+ countries | No | Yes | Yes | https://api.ibanforge.com |
| IEX Cloud | Realtime & Historical Stock and Market Data | apiKey | Yes | Yes | https://iexcloud.io/docs/api/ |
| IG | Spreadbetting and CFD Market Data | apiKey | Yes | Unknown | https://labs.ig.com/gettingstarted |
| Indian Mutual Fund | History of India Mutual Funds Data | No | Yes | Unknown | https://www.mfapi.in/ |
| Intrinio | Wide selection of financial data feeds | apiKey | Yes | Unknown | https://intrinio.com/ |
| Klarna | Klarna payment and shopping service | apiKey | Yes | Unknown | https://docs.klarna.com/klarna-payments/api/payments-api/ |
| MercadoPago | Mercado Pago integrations | apiKey | Yes | Unknown | https://www.mercadopago.com.br/developers/es/reference |
| Mono | Connect bank accounts / transaction data in Africa | apiKey | Yes | Unknown | https://mono.co/ |
| Moov | Send, receive, and store money | apiKey | Yes | Unknown | https://docs.moov.io/api/ |
| Nordigen | Bank account connection via official bank APIs | apiKey | Yes | Unknown | https://nordigen.com/en/account_information_documenation/integration/quickstart_guide/ |
| OpenFIGI | Equity, index, futures, options symbology from Bloomberg | apiKey | Yes | Yes | https://www.openfigi.com/api |
| Plaid | Connect bank accounts / transaction data | apiKey | Yes | Unknown | https://www.plaid.com/docs |
| Polygon | Historical stock market data | apiKey | Yes | Unknown | https://polygon.io/ |
| Portfolio Optimizer | Portfolio analysis and optimization | No | Yes | Yes | https://portfoliooptimizer.io/ |
| Razorpay IFSC | Indian Financial Systems Code (Bank Branch Codes) | No | Yes | Unknown | https://razorpay.com/docs/ |
| Real Time Finance | Websocket API for realtime stock data | apiKey | No | Unknown | https://github.com/Real-time-finance/finance-websocket-API/ |
| SEC EDGAR | Annual reports of public US companies | No | Yes | Yes | https://www.sec.gov/edgar/sec-api-documentation |
| SmartAPI | End-to-end broking services access | apiKey | Yes | Unknown | https://smartapi.angelbroking.com/ |
| StockData | Real-Time, Intraday & Historical Market Data, News, Sentiment | apiKey | Yes | Yes | https://www.StockData.org |
| Styvio | Realtime/historical stock data and sentiment | apiKey | Yes | Unknown | https://www.Styvio.com |
| Tax Data API | VAT number and tax validation | apiKey | Yes | Unknown | https://apilayer.com/marketplace/tax_data-api |
| Tradier | US equity/option market data | OAuth | Yes | Yes | https://developer.tradier.com |
| Twelve Data | Stock market data (real-time & historical) | apiKey | Yes | Unknown | https://twelvedata.com/ |
| VAT Validation | Validate VAT numbers and calculate VAT rates | apiKey | Yes | Yes | https://www.abstractapi.com/vat-validation-rates-api |
| WallstreetBets | WSB stock comments sentiment analysis | No | Yes | Unknown | https://dashboard.nbshare.io/apps/reddit/api/ |
| Yahoo Finance | Stock, crypto, currency exchange data | apiKey | Yes | Yes | https://www.yahoofinanceapi.com/ |
| YNAB | Budgeting & Planning | OAuth | Yes | Yes | https://api.youneedabudget.com/ |
| Zoho Books | Online accounting software | OAuth | Yes | Unknown | https://www.zoho.com/books/api/v3/ |

## Currency Exchange

| API | Description | Auth | HTTPS | CORS | URL |
|:---|:---|:---|:---|:---|:---|
| Currencylayer | Exchange rates and currency conversion | apiKey | Yes | Unknown | https://currencylayer.com |
| Exchangerate.host | Free foreign exchange & crypto rates | No | Yes | Unknown | https://exchangerate.host |
| Exchangeratesapi.io | Exchange rates with currency conversion | apiKey | Yes | Yes | https://exchangeratesapi.io |
| Fixer | Exchange rates and currency conversion | apiKey | No | Unknown | https://fixer.io |
| 1Forge | Forex currency market data | apiKey | Yes | Unknown | https://1forge.com/forex-data-api/api-documentation |
| Amdoren | Free currency API, 150+ currencies | apiKey | Yes | Unknown | https://www.amdoren.com/currency-api/ |
| Bank of Russia | Exchange rates and currency conversion | No | Yes | Unknown | https://www.cbr.ru/development/SXML/ |
| Currency-api | Free currency exchange rates, 150+ currencies, no rate limits | No | Yes | Yes | https://github.com/fawazahmed0/currency-api#readme |
| CurrencyFreaks | Current and historical currency exchange rates | apiKey | Yes | Yes | https://currencyfreaks.com/ |
| CurrencyScoop | Real-time and historical currency rates JSON API | apiKey | Yes | Yes | https://currencyscoop.com/api-documentation |
| Czech National Bank | Collection of exchange rates | No | Yes | Unknown | https://www.cnb.cz/cs/financni_trhy/devizovy_trh/kurzy_devizoveho_trhu/denni_kurz.xml |
| Economia.Awesome | Portuguese free currency prices and conversion | No | Yes | Unknown | https://docs.awesomeapi.com.br/api-de-moedas |
| ExchangeRate-API | Free currency conversion | apiKey | Yes | Yes | https://www.exchangerate-api.com |
| Frankfurter | Exchange rates, currency conversion and time series | No | Yes | Yes | https://www.frankfurter.app/docs |
| FreeForexAPI | Real-time FX rates for major currency pairs | No | Yes | No | https://freeforexapi.com/Home/Api |
| National Bank of Poland | Currency exchange rates (XML and JSON) | No | Yes | Yes | http://api.nbp.pl/en.html |
| paralelo.bo | Bolivia parallel-market USD/BOB rate | No | Yes | Yes | https://paralelo.bo/api |
| VATComply.com | Exchange rates, geolocation and VAT number validation | No | Yes | Yes | https://www.vatcomply.com/documentation |

## Government

| API | Description | Auth | HTTPS | CORS | URL |
|:---|:---|:---|:---|:---|:---|
| Charity Search | Non-profit charity data | apiKey | No | Unknown | http://charityapi.orghunter.com/ |
| Tenders in Hungary | Procurement data for Hungary (JSON) | No | Yes | Unknown | https://tenders.guru/hu/api |
| Tenders in Poland | Procurement data for Poland (JSON) | No | Yes | Unknown | https://tenders.guru/pl/api |
| Tenders in Romania | Procurement data for Romania (JSON) | No | Yes | Unknown | https://tenders.guru/ro/api |
| Tenders in Spain | Procurement data for Spain (JSON) | No | Yes | Unknown | https://tenders.guru/es/api |
| Tenders in Ukraine | Procurement data for Ukraine (JSON) | No | Yes | Unknown | https://tenders.guru/ua/api |

## Open Data

| API | Description | Auth | HTTPS | CORS | URL |
|:---|:---|:---|:---|:---|:---|
| Danish Energy Service | Open energy data from Energinet | No | Yes | Unknown | https://www.energidataservice.dk/ |
| National Grid ESO | Open data from Great Britain's Electricity System Operator | No | Yes | Unknown | https://data.nationalgrideso.com/ |
| SEC EDGAR Data | Annual reports of public US companies | No | Yes | Yes | https://www.sec.gov/edgar/sec-api-documentation |

## Environment

| API | Description | Auth | HTTPS | CORS | URL |
|:---|:---|:---|:---|:---|:---|
| BreezoMeter Pollen | Daily forecast pollen conditions | apiKey | Yes | Unknown | https://docs.breezometer.com/api-documentation/pollen-api/v2/ |
| Carbon Interface | Carbon (CO2) emissions estimates | apiKey | Yes | Yes | https://docs.carboninterface.com/ |
| Climatiq | Environmental footprint of emission-generating activities | apiKey | Yes | Yes | https://docs.climatiq.io |
| Cloverly | Impact of carbon-intensive activities in real time | apiKey | Yes | Unknown | https://www.cloverly.com/carbon-offset-documentation |
| CO2 Offset | Calculates and validates carbon footprint | No | Yes | Unknown | https://co2offset.io/api.html |
| GrünstromIndex | Green Power Index for Germany | No | No | Yes | https://gruenstromindex.de/ |
| IQAir | Air quality and weather data | apiKey | Yes | Unknown | https://www.iqair.com/air-pollution-data-api |
| Luchtmeetnet | Air quality for the Netherlands (RIVM) | No | Yes | Unknown | https://api-docs.luchtmeetnet.nl/ |
| OpenAQ | Open air quality data | apiKey | Yes | Unknown | https://docs.openaq.org/ |
| PM2.5 Open Data Portal | Open low-cost PM2.5 sensor data | No | Yes | Unknown | https://pm25.lass-net.org/#apis |
| PM25.in | Air quality of China | apiKey | No | Unknown | http://www.pm25.in/api_doc |
| PVWatts | Energy production for PV energy systems | apiKey | Yes | Unknown | https://developer.nrel.gov/docs/solar/pvwatts/v6/ |
| Srp Energy | Hourly usage energy report for SRP customers | apiKey | Yes | No | https://srpenergy-api-client-python.readthedocs.io/en/latest/api.html |
| UK Carbon Intensity | Official Carbon Intensity API for Great Britain | No | Yes | Unknown | https://carbon-intensity.github.io/api-definitions/ |
| Website Carbon | Estimate carbon footprint of loading web pages | No | Yes | Unknown | https://api.websitecarbon.com/ |

---

## Other categories in the upstream catalog

The full [`public-apis/public-apis`](https://github.com/public-apis/public-apis)
catalog also includes (approximate counts): Animals (~26), Anime (~19),
Anti-Malware (~15), Art & Design (~20), Authentication (~7), Books (~25),
Business (~24), Calendar (~15), Cloud Storage (~20), Continuous Integration (~6),
Cryptocurrency (60+), Development (100+), Dictionaries (~13), Documents &
Productivity (~26), Email (~20), Entertainment (~14), Events (~3), Food & Drink
(~24), Games & Comics (100+), Geocoding (50+), and many more (Health, Jobs,
Machine Learning, Music, News, Photography, Science, Sports, Transportation,
Weather, etc.).

These are out of scope for a GDP dashboard; consult the upstream repo if you need them.
