import sys
import re
import json
import codecs
import urllib.parse
import urllib.request
from time import time, sleep
from multiprocessing import Process, Queue
from lxml import html 
from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtWebEngine import *
from PyQt5.QtWebEngineWidgets import *

# this regular expression matches phones number in the following formats:
# (123) 456-7890, (123) 456.7890, 123-456-7890, and 123.456.7890
phoneReg = re.compile('((?:\()?\d{3}(?:-|\.| |\) )\d{3}(?:-|\.)\d{4})') #the period is a wildcard! Escape dat junt
emailReg = re.compile('[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,4}')
accessToken = {'token': '',
               'expires': 0}
aeMarket = '1M5CLqzJO4QQgrOiGZKCINcYB1WE39ByoZ2Rr-8WGIXw'
app = QApplication(sys.argv)

def httpRequest (url, headers, body, queryParams):
    if body == None:
        data = None
    else:
        data = urllib.parse.urlencode(body)
        data = data.encode('utf-8')
    if not queryParams == None:
        url += '?' + urllib.parse.urlencode(queryParams)
    print(url)
    req = urllib.request.Request(url, data, headers)
    reader = codecs.getreader("utf-8")
    try:
       response = urllib.request.urlopen(req)
       return json.load(reader(response))
    except urllib.error.HTTPError as e:
        print(e.code)

def getAccessToken():
    url = "https://www.googleapis.com/oauth2/v4/token"
    headers = {'Content-type': 'application/x-www-form-urlencoded'}
    body = {
        'refresh_token': '1/k8hHZdZt-Sl6KJ3htONsD8dEtbJGWt8w-vrOMDtz4uY',
        'client_id': '191133416807-lfh5rcsdom4ipmq7286gildecr2tjl8e.apps.googleusercontent.com',
        'client_secret': 'XGfZ9iDqhQFGvLCoumOsFIae',
        'grant_type': 'refresh_token'
    }
    response = httpRequest(url, headers, body, {})
    accessToken['token'] = response['access_token']
    accessToken['expires'] = response['expires_in'] + time()
    
def sheetValues(spreadSheet, sheet, range, values, queryParams):
    url = 'https://sheets.googleapis.com/v4/spreadsheets/'
    url += spreadSheet + '/values/'
    url += urllib.parse.quote("'" + sheet + "'" + '!' + range,"'!")
    headers = {'Authorization' : 'Bearer ' + accessToken['token']}
    response = httpRequest(url, headers, values, queryParams)
    return response
    
class LinkScrubber(object):
    def __init__(self, *args, **kwargs):
        pass

    def run(self, url, base, q):        
        p = Process(target=self.render, args=(url, base, q))
        processStart = time()
        p.start()
        self.data = []
        while p.is_alive():
            timeElapsed = time() - processStart            
            if timeElapsed > 30:
                print('Process has timed out. Aborting')
                p.terminate()
                app.quit() #maybe this isn't killing the same instance of Qapp as the thread, remember spawning a new process pretty much just starts the program again.
            else:   
                if not q.empty():          
                    self.data.append(q.get())             
        p.join()

    def render(self, url, base, q):
        self.q = q
        self.url = url
        self.base = base
        self.qt = QWebEnginePage()
        self.qt.loadStarted.connect(self._loadStarted)
        #self.qt.loadProgress.connect(self._loadProgress)
        self.qt.loadFinished.connect(self._loadFinished)
        self.qt.load(QUrl(url))
        app.exec_()

    def _loadStarted(self):
        print ('Load started.')

    def _loadProgress(self, progress):
        print ('Loading progress: ' + str(progress) + '%')

    def _loadFinished(self, result):
        print ('Load finished.')
        self.qt.toHtml(self.callable)

    def callable(self, data):
        self.html = data
        data = html.fromstring(data.encode())
        links = []        
        els = data.xpath('//a')
        for el in els:
            url = el.xpath("./@href") #the '.' indicates a local search
            title =  el.xpath("./text()")
            if len(url) == 0:
                continue 
            if url[0].find('/') == 0:
                url[0] = self.base + url[0]
            if self.base not in url[0]: #stay on same domain
                continue            
            links.append({'url': url[0], 'title': title[0] if len(title) > 0 else 'Link title not found'})        
        emails = emailReg.findall(self.html)  ##get email addresses
        numbers = phoneReg.findall(self.html)   ##get phone numbers
        for link in links:           
            self.q.put(['link', link])        
        for email in emails:           
            self.q.put(['email', email])
        for number in numbers:
            self.q.put(['number', number])
            
        # Data has been stored, it's safe to quit the app
        print ('All links placed in queue')
        app.quit()

class LinkCrawler(object):

        def __init__(self, link, base, depth, depthLimit, q, **kwargs):
            self.url = link['url']
            self.title = link['title']
            self.base = base
            self.depthLimit = depthLimit
            self.linkData = self.getLinkData()
            self.allLinks = []
            self.emails = []
            self.numbers = []
            self.sortData()            
            print ('Links found: ' + str(len(self.allLinks)))
            print ('Email addresses found: ' + str(len(self.emails)))
            for email in self.emails:
                print(email)
            print ('Phone numbers found: ' + str(len(self.numbers)))
            for number in self.numbers:
                print(number)
            self.validLinks = []
            self.invalidLinks = []
            self.verifyLinks()            
            self.depth = depth
            self.depthLimit = depthLimit
            self.children = []
            print('Spawning children..')
            self.spawnChildren()
            pass

        def getLinkData(self):
            l = LinkScrubber()
            l.run(self.url, self.base, q) 
            print ('Links recieved.')          
            return l.data         
            
        def sortData(self):            
            def isLink(link):
                if link['url'] not in allLinks:                    
                    self.allLinks.append(link)                    
                    allLinks.append(link['url'])
            def isEmail(email):
                if email not in allEmails:
                    self.emails.append(email)
                    allEmails.append(email)
            def isNumber(number):
                if number not in allNumbers:
                    self.numbers.append(number)
                    allNumbers.append(number)                    
            dataType = {'link': isLink, 'email': isEmail, 'number': isNumber}                 
            for datum in self.linkData:
                dataType[datum[0]](datum[1]) 

        def verifyLinks(self):
            for link in self.allLinks:                
                if QUrl(link['url']).isValid():
                    self.validLinks.append(link)
                else:
                    self.invalidLinks.append(link) 

        def spawnChildren(self):
            if self.depth < self.depthLimit:
                for link in self.validLinks:            
                    print('Visiting: ' + link['title'] + '\n' + link['url'] + '\n')
                    if link['url'] not in linksVisited:
                        self.children.append(LinkCrawler(link, self.base, self.depth + 1, self.depthLimit, q))
                    else:
                        print('This link has already been visited. Moving to next valid link.')
            else:
                print('Depth limit reached.\n') 
    
def getAllData(branch, key):    
    if len(branch.emails) > 0 or len(branch.numbers):    
        dataDict[key].append([branch.title, branch.url, branch.emails, branch.numbers])     
        
def traverse(branch, key):      
    for twig in branch.children:        
        traverse(twig, key)    
    getAllData(branch, key)  
    
if __name__ == '__main__':
    linksVisited = ''
    links = []
    allLinks = []  #this is used to record a link only once if it appears severals times on a single page
    allEmails = []
    allNumbers = []
    dataDict = {}
    q = Queue(maxsize=0)
    depthLimit = 1
    getAccessToken()
    linkArray = sheetValues(aeMarket, 'Links to Crawl', 'A2:A10', None, None)['values'] #sheet values are returned as 2d array
    for link in linkArray:
        links.append({'url': link[0],
            'title': ''})
    for link in links:
        linkTree = LinkCrawler(link, link['url'], 0, depthLimit, q)
        dataDict[link['url']] = []
        traverse(linkTree, link['url'])
    for key in dataDict:
        emails = []
        for page in dataDict[key]:
            emails.extend(page[2])#content-type must be set to application/json and body object must be json
    response = sheetValues(aeMarket, 'Email Addresses Found', 'A2:A' + str(1 + len(emails)), {'values': [emails]}, {'valueInputOption': 'RAW'})
    print(response)