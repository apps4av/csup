import common

import cycle

start_date = cycle.get_version_start(cycle.get_cycle_download())  # to download which cycle
edition = start_date.replace("-", "")

all_charts = common.list_crawl("https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/dafd/",
                               "^http.*DCS_" + edition + ".zip$")
# download
common.download_list(all_charts)

# Cover-to-cover Chart Supplement PDF for each region, e.g.
# https://aeronav.faa.gov/Upload_313-d/supplements/CS_AK_20261029.pdf
covers = [
    "https://aeronav.faa.gov/Upload_313-d/supplements/CS_{0}_{1}.pdf".format(region, edition)
    for region in common.states_in_regions
]
common.download_list(covers)

# Do DCS
common.make_csup()
common.zip_csup(edition)
