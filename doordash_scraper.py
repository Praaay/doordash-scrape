import asyncio
import json
import os
from scrapybara import Scrapybara
from undetected_playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

async def get_scrapybara_browser():
    client = Scrapybara(api_key=os.getenv("SCRAPYBARA_API_KEY"))
    for _ in range(3):  # at most to 3 times
        try:
            instance = client.start_browser()
            return instance
        except Exception as e:
            print(f"Error starting browser: {e}")
            await asyncio.sleep(2)
    raise RuntimeError("Failed to start Scrapybara browser after 3 attempts")

async def set_delivery_address(page, address: str):
    print("Opening address editor...")
    # Ensure the button is present before we click it:
    await page.wait_for_selector('button[data-testid="addressTextButton"]', timeout=5000)
    await page.click('button[data-testid="addressTextButton"]')

    print("Filling in the address field...")
    await page.wait_for_selector('input[data-testid="AddressAutocompleteField"]', timeout=3000)
    await page.fill('input[data-testid="AddressAutocompleteField"]', address)
    await asyncio.sleep(2)

    print("Selecting first autocomplete result...")
    await page.keyboard.press("ArrowDown")
    await page.keyboard.press("Enter")

    print("Saving address...")
    await page.click('[data-anchor-id="AddressEditSave"]')
    
    print("Waiting for page to confirm address change...")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(2)

    # Debug: Verify the address is actually set
    try:
        address_text = await page.inner_text('button[data-testid="addressTextButton"]')
        print(f"Address confirmed: {address_text}")
    except Exception as e:
        print(f"Error verifying address: {e}")
    
async def retrieve_menu_items(instance, start_url: str) -> list[dict]:
    """
    :args:
    instance: the scrapybara instance to use
    url: the initial url to navigate to

    :desc:
    this function navigates to {url}. then, it will collect the detailed
    data for each menu item in the store and return it.

    (hint: click a menu item, open dev tools -> network tab -> filter for
            "https://www.doordash.com/graphql/itemPage?operation=itemPage")

    one way to do this is to scroll through the page and click on each menu
    item.

    determine the most efficient way to collect this data.

    :returns:
    a list of menu items on the page, represented as dictionaries
    """
    menu_data = []
    max_attempts = 3
    success = False

    for attempt in range(1, max_attempts + 1):
        print(f"\n--- Attempt #{attempt} ---")

        # Start a fresh browser instance
        instance = await get_scrapybara_browser()
        cdp_url = instance.get_cdp_url().cdp_url

        async with async_playwright() as p:
            try:
                browser = await p.chromium.connect_over_cdp(cdp_url)
            except Exception as e:
                print(f"Error connecting via CDP: {e}")
                instance.stop()
                continue

            page = await browser.new_page()
            response_future = asyncio.Future()

            async def handle_response(response):
                if ("/graphql/storepageItemLists?operation=storepageItemLists" in response.url and
                    response.request.method == "POST"):
                    print("Captured storepageItemLists POST request!")
                    try:
                        json_data = await response.json()
                        item_lists = json_data.get("data", {}).get("storepageFeed", {}).get("itemLists", [])
                        total_items = 0
                        for category in item_lists:
                            category_name = category.get('name', 'Uncategorized')
                            items = category.get('items', [])
                            total_items += len(items)
                            print(f"Category: {category_name}, items: {len(items)}")
                            for item in items:
                                menu_data.append({
                                    'id': item['id'],
                                    'name': item['name'],
                                    'category': category_name,
                                    'description': item.get('description'),
                                    'price': item.get('displayPrice'),
                                    'image_url': item.get('imageUrl'),
                                    'rating': item.get('ratingDisplayString'),
                                    'badges': [badge['title'] for badge in item.get('badges', [])],
                                    'store_id': item.get('storeId')
                                })
                        if not response_future.done():
                            response_future.set_result(True)
                    except Exception as e:
                        print(f"Error processing response: {str(e)}")
                        if not response_future.done():
                            response_future.set_result(False)

            page.on('response', handle_response)

            print("Navigating to store page...")
            try:
                await page.goto(start_url, wait_until="networkidle")
            except Exception as e:
                print(f"Error during page.goto: {e}")
                await browser.close()
                instance.stop()
                continue

            print("Setting delivery address...")
            try:
                await set_delivery_address(page, "1600 Pennsylvania Ave NW, Washington, DC")
            except Exception as e:
                print(f"Error during set_delivery_address: {e}")
                await browser.close()
                instance.stop()
                continue

            print("⏳ Waiting for `storepageItemLists` request...")
            try:
                await asyncio.wait_for(response_future, timeout=15)
                print("🎉 storepageItemLists request captured!")
                success = True
                await browser.close()
                instance.stop()
                break
            except asyncio.TimeoutError:
                print(f"⚠️ Attempt #{attempt} timed out (no storepageItemLists).")
                await browser.close()
                instance.stop()
                # Try next attempt

    if not success:
        print("🚨 All attempts exhausted; no data received.")

    return menu_data

        # browser automation ...


async def main():
    instance = await get_scrapybara_browser()
    try:
        # await retrieve_menu_items(
        #     instance,
        #     "https://www.doordash.com/store/panda-express-san-francisco-980938/12722988/?event_type=autocomplete&pickup=false",
        # )
        retrieve_data = await retrieve_menu_items(
            instance,
            "https://www.doordash.com/store/panda-express-san-francisco-980938/12722988/?event_type=autocomplete&pickup=false",
        )
        # Write the menu_data to a JSON file
        with open("retrieve_data.json", "w", encoding="utf-8") as f:
            json.dump(retrieve_data, f, ensure_ascii=False, indent=2)
        print("Menu data has been saved to retrieve_data.json")
    finally:
        # Be sure to close the browser instance after you're done!
        instance.stop()


if __name__ == "__main__":
    asyncio.run(main())