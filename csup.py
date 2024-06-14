import common

import cycle

start_date = cycle.get_version_start(cycle.get_cycle_download())  # to download which cycle

all_charts = common.list_crawl("https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/dafd/", "^http.*DCS_.*zip$")
# download
common.download_list(all_charts)

# Do DCS
common.make_csup()
common.zip_csup()
