# set up
rye init

# activate environment
source .venv/bin/activate

rye add scrapybara
rye add undetected-playwright-patch

python doordash_scraper.py

add .env file to put the API_KEY
