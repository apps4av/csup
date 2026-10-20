import glob
import os
import urllib.request
import re
from subprocess import check_call, check_output
from bs4 import BeautifulSoup
import zipfile
from tqdm import tqdm
import xml.etree.ElementTree as et
import concurrent.futures
import cycle


states_in_regions = {
    "AK":  ["AK",],
    "PAC": ["HI", "XX"],
    "NW":  ["WA", "MT", "WY", "ID", "OR"],
    "SW":  ["CA", "NV", "UT", "CO", "NM", "AZ"],
    "NC":  ["ND", "MN", "IA", "MO", "KS", "NE", "SD"],
    "EC":  ["WI", "MI", "OH", "IN", "IL"],
    "SC":  ["OK", "AR", "MS", "LA", "TX"],
    "NE":  ["NY", "ME", "VT", "NH", "MA", "RI", "CT", "NJ", "DE", "MD", "DC", "VA", "WV", "PA"],
    "SE":  ["KY", "NC", "SC", "GA", "FL", "AL", "TN", "PR", "VI"]
}


def list_crawl(url, match):
    charts = []
    html_page = urllib.request.urlopen(url)
    soup = BeautifulSoup(html_page, "html.parser")
    for link in tqdm(soup.findAll('a'), desc="Scanning website links"):
        link_x = link.get('href')
        if link_x is None:
            continue
        if re.search(match, link_x):
            charts.append(link_x)
    list_set = set(charts)  # unique
    return list(list_set)


def download(url):
    name = url.split("/")[-1]
    # check if exists
    if not os.path.isfile(name):
        urllib.request.urlretrieve(url, name)
    if name.endswith(".zip") or name.endswith(".ZIP"):  # if a zipfile, unzip first
        with zipfile.ZipFile(name, 'r') as zip_ref:
            zip_ref.extractall(".")


def download_list(charts):
    for cc in tqdm(range(len(charts)), desc="Downloading/unzipping"):
        download(charts[cc])


def call_script(script):
    check_call([script], shell=True)


def call_script_return(script):
    return check_output([script], shell=True, encoding='utf8').strip()


def call_perl_script(script):
    check_call(["perl" + " " + script + ".pl > " + script + ".csv"], shell=True)


def read_csup_xml():
    xml_file = glob.glob("afd_*.xml")[0]
    tree = et.parse(xml_file)
    root = tree.getroot()
    # Find all "airport" elements
    airport_elements = root.findall(".//airport")
    return airport_elements


def process_csup(airport):
    apt_id = airport.find('aptid').text
    pages = airport.find('pages')
    pdfs = pages.findall('pdf')

    if apt_id is None:
        return

    apt_dir = "afd/" + apt_id
    os.makedirs(apt_dir, exist_ok=True)

    # page is a new CS e.g. notices
    page = 0
    for pdf in pdfs:
        fn = pdf.text.upper()

        tokens = fn.split("_")
        base = ("CSUP-" + tokens[0]).upper()  # add region to name

        cmd = f'mogrify -trim +repage -dither none -antialias -density 225 -depth 8 -background white  -alpha remove -alpha off -colors 15 -format png -quality 100 -write {apt_dir}/{base}_{page}.png {fn}'
        call_script(cmd)
        page = page + 1


def make_csup():
    os.makedirs("afd", exist_ok=True)

    # make all files upper case, FAA mixes cases
    files = glob.glob("*.pdf")
    for file in files:
        os.rename(file, file.upper())

    airports = read_csup_xml()

    # submit 8 jobs at a time
    sub_lists = [airports[i:i + 8] for i in range(0, len(airports), 8)]

    for sublist in tqdm(sub_lists, desc="Processing CSUP"):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(process_csup, elem) for elem in sublist]
            # Collect the results
            [future.result() for future in concurrent.futures.as_completed(futures)]


def _cover_pdf_source(region, edition):
    """Local path of the downloaded cover-to-cover PDF (``CS_AK_20261029.pdf``).

    ``make_csup`` uppercases every ``*.pdf`` in the work directory, so accept
    either case.
    """
    name = "CS_{0}_{1}.pdf".format(region, edition)
    for candidate in (name, name.upper()):
        if os.path.isfile(candidate):
            return candidate
    raise FileNotFoundError("Missing cover-to-cover Chart Supplement PDF: " + name)


def zip_csup(edition):
    # US geo regions
    regions = list(states_in_regions.keys())
    zip_files = []
    manifest_files = []

    for region in regions:
        try:
            os.remove(region + "_CSUP" + ".zip")
            os.remove(region + "_CSUP")
        except FileNotFoundError as e:
            pass

    for region in regions:
        zip_files.append(zipfile.ZipFile(region + "_CSUP" + ".zip", "w"))
        manifest_files.append(open(region + "_CSUP", "w+"))

    for ff in manifest_files:
        ff.write(cycle.get_cycle() + "\n")

    for count in range(len(regions)):
        region = regions[count]
        file_list = glob.glob("*/CSUP-" + region + "_*", root_dir="afd/", recursive=True)
        for ff in tqdm(file_list, desc="Zipping CSUP-" + region):
            zip_files[count].write("afd/" + ff)
            manifest_files[count].write("afd/" + ff + "\n")

        # Complete regional PDF at the zip root (AK_CSUP.pdf), not under afd/.
        # Documents lists PDFs in the app data root only.
        cover_name = region + "_CSUP.pdf"
        zip_files[count].write(_cover_pdf_source(region, edition), arcname=cover_name)
        manifest_files[count].write(cover_name + "\n")

    for ff in manifest_files:
        ff.close()

    for count in range(len(regions)):
        zip_files[count].write(regions[count] + "_CSUP")
        zip_files[count].close()

