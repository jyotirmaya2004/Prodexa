def _load_scraper_clean():
	from scraper_clean import (
		get_driver as clean_get_driver,
		scrape_flipkart as clean_scrape_flipkart,
		scrape_amazon as clean_scrape_amazon,
		scrape_myntra as clean_scrape_myntra,
		scrape_meesho as clean_scrape_meesho,
		scrape_all_sites as clean_scrape_all_sites,
	)

	return {
		"get_driver": clean_get_driver,
		"scrape_flipkart": clean_scrape_flipkart,
		"scrape_amazon": clean_scrape_amazon,
		"scrape_myntra": clean_scrape_myntra,
		"scrape_meesho": clean_scrape_meesho,
		"scrape_all_sites": clean_scrape_all_sites,
	}


def get_driver():
	return _load_scraper_clean()["get_driver"]()


def scrape_flipkart(query):
	return _load_scraper_clean()["scrape_flipkart"](query)


def scrape_amazon(query):
	return _load_scraper_clean()["scrape_amazon"](query)


def scrape_myntra(query):
	return _load_scraper_clean()["scrape_myntra"](query)


def scrape_meesho(query):
	return _load_scraper_clean()["scrape_meesho"](query)


def scrape_all_sites(query):
	return _load_scraper_clean()["scrape_all_sites"](query)
