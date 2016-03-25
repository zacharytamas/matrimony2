#!/usr/bin/env python

import json
import webapp2
import logging

from spreadsheet_api import SpreadsheetService


class RSVPHandler(webapp2.RequestHandler):
  """Handler for RSVP actions."""

  def guestLookup(self):
    service = SpreadsheetService()
    code = self.request.get('code')

    if code:
      guestInfo = service.guestLookup(code)
      self.response.write(json.dumps(guestInfo, indent=4))

  def respond(self):
    service = SpreadsheetService()
    code = self.request.get('code')
    attending = self.request.get('attending')
    headcount = self.request.get('headcount')
    meal_preference = self.request.get("mealPreference")

    if not all([code, attending, headcount, meal_preference or True]):
      # logging.error("Invalid request to the respond endpoint...")
      # TODO Return an InvalidRequest
      self.response.write(json.dumps({
        'error': 'whoops'
      }))
      return

    response = service.RSVP(code,
                            attending == "yes",
                            headcount,
                            meal_preference)

    self.response.write(json.dumps(response, indent=4))

app = webapp2.WSGIApplication([
  webapp2.Route('/api/rsvp/guest-lookup/', RSVPHandler, handler_method='guestLookup'),
  # TODO Make respond POST-only
  webapp2.Route('/api/rsvp/respond/',      RSVPHandler, handler_method='respond'),
], debug=False)
