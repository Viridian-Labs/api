from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
import time

# Initialize Chrome with maximized window
options = webdriver.ChromeOptions()
options.add_argument('--start-maximized')
browser = webdriver.Chrome(options=options)

urls = [
    "https://equilibrefinance.com/swap",
    "https://equilibrefinance.com/pools",
    "https://equilibrefinance.com/dashboard",
]

wait = WebDriverWait(browser, 10)  # Wait for up to 10 seconds
total_time = 0

try:

    for url in urls:
        browser.get(url)

        # If the current URL is for 'pools' or 'dashboard', wait for the table data
        if "pools" in url or "dashboard" in url:
            try:
                # Wait until a table with at least 1 row appears
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table tr")))
            except Exception as e:
                print(f"Error while waiting for table data on {url}: {str(e)}")

        # Find all button elements on the page
        buttons = browser.find_elements(By.TAG_NAME, "button")

        # Click each button with a delay between clicks, avoiding certain buttons
        for button in buttons:
            try:
                # Avoid buttons with 'Connect Wallet' text or 'chakra-menu__menu-button' class
                # And only click if button is displayed and enabled
                if ('Connect Wallet' not in button.text and 
                    'chakra-menu__menu-button' not in button.get_attribute('class') and
                    button.is_displayed() and 
                    button.is_enabled()):
                    button.click()
                    time.sleep(1)  # Pauses for 1 second
            except StaleElementReferenceException:
                #print(f"Button updated on the page while trying to click on {url}. Moving on...")
                pass
            except Exception as e:
                print(f"Error clicking button on {url}: {str(e)}")        

        # Execute JavaScript to get the performance timing
        try:
            navigation_start = browser.execute_script("return window.performance.timing.navigationStart")
            dom_complete = browser.execute_script("return window.performance.timing.domComplete")

            load_time = dom_complete - navigation_start
            total_time += load_time  # accumulate the total time
            print(f"Time taken to load {url}: {load_time}ms")
        except Exception as e:
            print(f"Error retrieving load time for {url}: {str(e)}")

    print(f"Total time taken for all URLs: {total_time}ms")
    browser.quit()
    
except Exception as e:
    # handle the exception quietly, or log it without printing the entire stack trace.
    print(f"Error: {str(e)}")
