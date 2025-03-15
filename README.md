# set up
rye init

# activate environment
source .venv/bin/activate

#rye add
rye add scrapybara

rye add undetected-playwright-patch

#how to run the script
python doordash_scraper.py

#important
add .env file to put the API_KEY
