import gspread
import json
import logging
import re
from google.appengine.api import memcache
from oauth2client.client import SignedJwtAssertionCredentials

# credentials.json file from Google Cloud Console.
# See: http://gspread.readthedocs.org/en/latest/oauth2.html
CONFIG = json.load(open('credentials.json'))
scope = ['https://spreadsheets.google.com/feeds']

credentials = SignedJwtAssertionCredentials(CONFIG['client_email'],
  CONFIG['private_key'].encode(), scope)

DATA_WORKSHEET_NAME = "Data"
COL_INFO_NAME_PRIMARY = 1

COL_NAMES = [
  "primaryName",
  "mailingName",
  "expectedGuests",
  "expectedHeadCount",
  "brideOrGroom",
  "category",
  "addressStreet",
  "addressCity",
  "addressState",
  "addressZipCode",
  "sdEnvelopePrinted",
  "-",
  "rsvpCode",
  "rsvpResponseMethod",
  "rsvpAttending",
  "rsvpHeadcount",
  "rsvpMealPreference",
  "rsvpGuestNames",
]

COL_INDEXES = {}
COL_LETTERS = {}

# NOTE This just dynamically generates all the column indexes with their
# names from above. This is easier in case I need to change the schema of
# my spreadsheet later: I can just enter the new column in the list above
# in its appropriate place and not have to worry about recalculating all
# the indexes.
def magicIndexes():
  count = 1
  for name in COL_NAMES:
    COL_INDEXES[name] = count
    # This little hack will work as long as we stay under 26 columns
    COL_LETTERS[name] = chr((count - 1) + ord("A"))
    count += 1
magicIndexes()

SHARED_SERVICE = None
SERVICE_CACHE_KEY = 'gspread'


def get_service():
  service = memcache.get(SERVICE_CACHE_KEY)
  if service is None:
    service = gspread.authorize(credentials)
    memcache.add(key=SERVICE_CACHE_KEY, value=service, time=3600)
  return service


class SpreadsheetService(object):

  spreadsheet_id = CONFIG['spreadsheet_id']  # For privacy.

  service = None
  spreadsheet = None
  worksheet = None

  def __init__(self):
    self.service = get_service()
    self.__getSpreadsheet()

  def __getSpreadsheet(self):
    if self.spreadsheet is None or self.worksheet is None:
      self.spreadsheet = self.service.open_by_key(self.spreadsheet_id)
      self.worksheet = self.spreadsheet.worksheet(DATA_WORKSHEET_NAME)

  def __findRowForCode(self, code):
    """Finds the row of the spreadsheet which corresponds to a
    given RSVP code."""

    # Find the number in the code and convert it to an integer.
    # Codes come in a format like this: `JONES5` where the final number
    # is the spreadsheet row number. This lets us find it in constant time.
    row_number = map(lambda e: int(e), re.findall('\d+', code))
    if len(row_number):
      return row_number[0]

  def __fetchRowByNumberWithCode(self, row_number, code):
    """Fetches a row by number, verifies it matches the code, and returns
    it if it does."""
    # Now that we have a row number, let's make sure that it actually
    # matches. If it doesn't, we implicitly return None.
    row = self.worksheet.row_values(row_number)
    if row and self.__getValueFromRow(row, 'rsvpCode').lower() == code.lower():
      return row

  def __writeValue(self, row_number, col_name, value):
    """Convenience method for writing a value to the spreadsheet."""
    self.worksheet.update_cell(row_number, COL_INDEXES[col_name], value)

  def __getValueFromRow(self, row, col_name):
    """Just a convenience accessor to get values from
    certain columns of a row."""
    try:
      return row[COL_INDEXES[col_name] - 1]
    except IndexError:
      return None

  def guestLookup(self, code):
    """Returns information about a guest based on their invite code."""
    row_number = self.__findRowForCode(code)
    row = self.__fetchRowByNumberWithCode(row_number, code)

    if not row:
      return {
        "status": "failed",
        "message": "A guest with that invite code was not found."
      }

    return {
      "status": "success",
      "guest": {
        "code": code,
        "primaryName": self.__getValueFromRow(row, "primaryName"),
        "expectedGuests": self.__getValueFromRow(row, "expectedGuests")
      }
    }

  def RSVP(self, code, attending, headcount, guests, meal_preference=""):
    row_number = self.__findRowForCode(code)
    row = self.__fetchRowByNumberWithCode(row_number, code)

    if not row:
      return {
        'status': 'invalid',
        'fields': ['rsvpCode']
      }

    rsvp_range = "%s%d:%s%d" % (COL_LETTERS["rsvpResponseMethod"], row_number,
                                COL_LETTERS["rsvpGuestNames"], row_number)

    # This quirky method allows us to update them in a batch.
    selection = self.worksheet.range(rsvp_range)
    values = [
      "Online",
      "YES" if attending else "NO",
      headcount if attending else 0,
      meal_preference,
      guests
    ]

    for cell, value in zip(selection, values):
      cell.value = value

    self.worksheet.update_cells(selection)

    return {
      'status': 'success'
    }
