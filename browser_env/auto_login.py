"""Script to automatically login each website"""
import argparse
import glob
import os
import time
from concurrent.futures import ThreadPoolExecutor
from itertools import combinations
from pathlib import Path

from ezcolorlog import root_logger as logger
from playwright.sync_api import sync_playwright

from .env_config import (
    ACCOUNTS,
    GITLAB,
    REDDIT,
    SHOPPING,
    SHOPPING_ADMIN,
)

HEADLESS = True
SLOW_MO = 0


SITES = ["gitlab", "shopping", "shopping_admin", "reddit"]
URLS = [
    f"{GITLAB}/-/profile",
    f"{SHOPPING}/wishlist/",
    f"{SHOPPING_ADMIN}/dashboard",
    f"{REDDIT}/user/{ACCOUNTS['reddit']['username']}/account",
]
EXACT_MATCH = [True, True, True, True]
KEYWORDS = ["", "", "Dashboard", "Delete"]


assert len(SITES) == len(URLS) == len(EXACT_MATCH) == len(KEYWORDS)
logger.info(f"Configured sites: {SITES}")

def is_expired(
    storage_state: Path, url: str, keyword: str, url_exact: bool = True
) -> bool:
    """Test whether the cookie is expired"""
    logger.info(f"Checking if cookie is expired for {storage_state} -> {url}")
    
    if not storage_state.exists():
        logger.warning(f"Storage state file does not exist: {storage_state}")
        return True

    try:
        context_manager = sync_playwright()
        playwright = context_manager.__enter__()
        browser = playwright.chromium.launch(headless=True, slow_mo=SLOW_MO)
        context = browser.new_context(storage_state=storage_state)
        page = context.new_page()
        
        logger.debug(f"Navigating to {url}")
        page.goto(url)
        time.sleep(1)
        d_url = page.url
        content = page.content()
        context_manager.__exit__()
        
        if keyword:
            is_expired = keyword not in content
            logger.info(f"Keyword '{keyword}' {'not found' if is_expired else 'found'} in content")
            return is_expired
        else:
            if url_exact:
                is_expired = d_url != url
                logger.info(f"URL exact match: expected '{url}', got '{d_url}' -> {'expired' if is_expired else 'valid'}")
                return is_expired
            else:
                is_expired = url not in d_url
                logger.info(f"URL contains check: '{url}' {'not in' if is_expired else 'in'} '{d_url}' -> {'expired' if is_expired else 'valid'}")
                return is_expired
    except Exception as e:
        logger.error(f"Error checking cookie expiration for {storage_state}: {e}", exc_info=True)
        return True


def renew_comb(comb: list[str], auth_folder: str = "./.auth") -> None:
    """Renew authentication for a combination of sites"""
    logger.info(f"Starting authentication renewal for sites: {comb}")
    
    try:
        context_manager = sync_playwright()
        playwright = context_manager.__enter__()
        browser = playwright.chromium.launch(headless=HEADLESS)
        context = browser.new_context()
        page = context.new_page()

        if "shopping" in comb:
            logger.info("Logging into shopping site")
            username = ACCOUNTS["shopping"]["username"]
            password = ACCOUNTS["shopping"]["password"]
            page.goto(f"{SHOPPING}/customer/account/login/")
            page.get_by_label("Email", exact=True).fill(username)
            page.get_by_label("Password", exact=True).fill(password)
            page.get_by_role("button", name="Sign In").click()

        if "reddit" in comb:
            logger.info("Logging into reddit site")
            username = ACCOUNTS["reddit"]["username"]
            password = ACCOUNTS["reddit"]["password"]
            page.goto(f"{REDDIT}/login")
            page.get_by_label("Username").fill(username)
            page.get_by_label("Password").fill(password)
            page.get_by_role("button", name="Log in").click()

        if "classifieds" in comb:
            raise NotImplementedError("Classifieds is not implemented")
            # logger.info("Logging into classifieds site")
            # username = ACCOUNTS["classifieds"]["username"]
            # password = ACCOUNTS["classifieds"]["password"]
            # page.goto(f"{CLASSIFIEDS}/index.php?page=login")
            # page.locator("#email").fill(username)
            # page.locator("#password").fill(password)
            # page.get_by_role("button", name="Log in").click()

        if "shopping_admin" in comb:
            logger.info("Logging into shopping admin site")
            username = ACCOUNTS["shopping_admin"]["username"]
            password = ACCOUNTS["shopping_admin"]["password"]
            page.goto(f"{SHOPPING_ADMIN}")
            page.get_by_placeholder("user name").fill(username)
            page.get_by_placeholder("password").fill(password)
            page.get_by_role("button", name="Sign in").click()

        if "gitlab" in comb:
            logger.info("Logging into gitlab site")
            username = ACCOUNTS["gitlab"]["username"]
            password = ACCOUNTS["gitlab"]["password"]
            page.goto(f"{GITLAB}/users/sign_in")
            page.get_by_test_id("username-field").click()
            page.get_by_test_id("username-field").fill(username)
            page.get_by_test_id("username-field").press("Tab")
            page.get_by_test_id("password-field").fill(password)
            page.get_by_test_id("sign-in-button").click()

        # Ensure auth folder exists
        os.makedirs(auth_folder, exist_ok=True)
        
        state_file = f"{auth_folder}/{'.'.join(comb)}_state.json"
        context.storage_state(path=state_file)
        logger.info(f"Authentication state saved to: {state_file}")

        context_manager.__exit__()
        logger.info(f"Successfully renewed authentication for sites: {comb}")
        
    except Exception as e:
        logger.error(f"Error during authentication renewal for {comb}: {e}", exc_info=True)
        raise


def get_site_comb_from_filepath(file_path: str) -> list[str]:
    comb = os.path.basename(file_path).rsplit("_", 1)[0].split(".")
    return comb


def main(auth_folder: str = "./.auth") -> None:
    logger.info("Starting main authentication process")
    
    pairs = list(combinations(SITES, 2))
    logger.info(f"Generated {len(pairs)} site pairs for authentication: {pairs}")
    # remove incompatible pairs
    pairs = [pair for pair in pairs if not ("reddit" in pair and ("shopping" in pair or "shopping_admin" in pair))]
    logger.info(f"Filtered to {len(pairs)} site pairs for authentication: {pairs}")

    with ThreadPoolExecutor(max_workers=8) as executor:
        for pair in pairs:
            # Auth doesn't work on this pair as they share the same cookie
            if "reddit" in pair and (
                "shopping" in pair or "shopping_admin" in pair
            ):
                logger.info(f"Skipping incompatible pair: {pair}")
                continue
            logger.info(f"Submitting authentication task for pair: {pair}")
            executor.submit(
                renew_comb, list(sorted(pair)), auth_folder=auth_folder
            )

        for site in SITES:
            logger.info(f"Submitting authentication task for single site: {site}")
            executor.submit(renew_comb, [site], auth_folder=auth_folder)
    
    logger.info("Starting cookie expiration validation")
    # parallel checking if the cookies are expired  
    futures = []
    future_to_cookie_file = {}  # Track which cookie file each future corresponds to
    cookie_files = list(glob.glob(f"{auth_folder}/*.json"))
    logger.info(f"Found {len(cookie_files)} cookie files to validate")
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        for c_file in cookie_files:
            comb = get_site_comb_from_filepath(c_file)
            logger.debug(f"Validating cookie file: {c_file} for sites: {comb}")
            for cur_site in comb:
                url = URLS[SITES.index(cur_site)]
                keyword = KEYWORDS[SITES.index(cur_site)]
                match = EXACT_MATCH[SITES.index(cur_site)]
                future = executor.submit(
                    is_expired, Path(c_file), url, keyword, match
                )
                futures.append(future)
                future_to_cookie_file[future] = c_file

    logger.info("Checking validation results")
    for i, future in enumerate(futures):
        try:
            result = future.result()
            cookie_file = future_to_cookie_file[future]
            if result:
                logger.error(f"Cookie {cookie_file} expired.")
            else:
                logger.info(f"Cookie {cookie_file} is valid.")
            assert not result, f"Cookie {cookie_file} expired."
        except Exception as e:
            cookie_file = future_to_cookie_file[future]
            logger.error(f"Error validating cookie {cookie_file}: {e}", exc_info=True)
            raise
    
    logger.info("Authentication process completed successfully")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--site_list", nargs="+", default=[])
    parser.add_argument("--auth_folder", type=str, default="./.auth")
    args = parser.parse_args()
    
    logger.info(f"Starting auto_login with args: {args}")
    
    if not args.site_list:
        main()
    else:
        logger.info(f"Renewing authentication for specific sites: {args.site_list}")
        renew_comb(args.site_list, auth_folder=args.auth_folder)
