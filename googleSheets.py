import json
import codecs
import urllib.parse
import urllib.request
from time import time

def getAccessToken(accessToken):
    url = "https://www.googleapis.com/oauth2/v4/token"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    body = {
        'refresh_token': '1/uKAabOeXjjSm0EXXAnGV1R5AudNT-yQ7kOxnj3Ar1AgSk6WEsker4uzn_J7Ais2j',
        'client_id': '21863320594-32clib022ec4b2kb5mcvldhsspqfdd35.apps.googleusercontent.com',
        'client_secret': 'Al3Km_ngrqchaVw3dk3FF5FU',
        'grant_type': 'refresh_token'
    }
    response = httpRequest(url, headers, body, {}, 'POST')
    accessToken['token'] = response['access_token']
    accessToken['expires'] = response['expires_in'] + time()
    return accessToken
    
def sheetValues(spreadSheet, sheet, range, values, headers, queryParams, method, accessToken):
    url = 'https://sheets.googleapis.com/v4/spreadsheets/'
    url += spreadSheet + '/values/'
    url += urllib.parse.quote(sheet +  '!' + range,"'!")
    headers['Authorization'] = 'Bearer ' + accessToken['token']
    response = httpRequest(url, headers, values, queryParams, method)
    return response
    
def httpRequest (url, headers, body, queryParams, method):
    if body == None:
        data = None
    elif headers['Content-Type'] == 'application/json':
        data = json.dumps(body).encode('utf8')
    else:
        data = urllib.parse.urlencode(body)
        data = data.encode('utf-8')
    if not queryParams == None:
        url += '?' + urllib.parse.urlencode(queryParams)
    req = urllib.request.Request(url, data, headers, None, False, method)
    reader = codecs.getreader("utf-8")
    try:
       response = urllib.request.urlopen(req)
       return json.load(reader(response))
    except urllib.error.HTTPError as e:
        # do something
        print('Error code: ', e.code)
    except urllib.error.URLError as e:
        # do something
        print('Reason: ', e.reason)
        
def moveLinkToComplete(linkCrawled, aeMarket, emailSource, accessToken):
    linkData = sheetValues(aeMarket, emailSource, 'A2:B', None, {}, None, 'GET', accessToken) #sheet values are returned as 2d array
    if 'values' in linkData.keys():
        if linkData['values'][0][0] == linkCrawled['url']:
            linkData['values'].pop(0)
            if len(linkData['values']) == 0:
                linkData['values'] = [['','']]
            else:
                linkData['values'].append(['', ''])
            headers = {"Content-Type": "application/json"}
            body = {'values': linkData['values'], 'majorDimension': 'ROWS'}
            response = sheetValues(aeMarket, emailSource, 'A2:B' + str(len(linkData['values']) + 1), body, headers, {'valueInputOption': 'RAW'}, 'PUT', accessToken)
            print(response)
    linkComplete = [linkCrawled['url'], json.dumps(linkCrawled['data'])]
    linksCompleted = sheetValues(aeMarket, emailSource, 'C2:D', None, {}, None, 'GET', accessToken)
    if 'values' in linksCompleted.keys():
        linksCompleted['values'].append(linkComplete)
    else:
        linksCompleted = {}
        linksCompleted['values'] = [linkComplete]
    headers = {"Content-Type": "application/json"}
    body = {'values': linksCompleted['values'], 'majorDimension': 'ROWS'}
    response = sheetValues(aeMarket, emailSource, 'C2:D' + str(len(linksCompleted['values']) + 1), body, headers, {'valueInputOption': 'RAW'}, 'PUT', accessToken)
    print(response)