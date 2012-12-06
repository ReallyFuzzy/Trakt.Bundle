import re
import cerealizer
import urllib
import urllib2
import copy
import sys
import base64

from datetime       import date, datetime, timedelta
from dateutil       import tz
from sets           import Set

from BeautifulSoup  import BeautifulSoup

VIDEO_PREFIX = "/video/trakt"
NAME = "Trakt"

# make sure to replace artwork with what you want
# these filenames reference the example files in
# the Contents/Resources/ folder in the bundle
ART	 = 'art-default.jpg'
APP_ICON = 'icon-default.png'

ADDITIONAL_SOURCES_KEY = "ADDITIONAL_SOURCES"

USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_2) AppleWebKit/534.51.22 (KHTML, like Gecko) Version/5.1.1 Safari/534.51.22'

TRAKT_URL = "http://api.trakt.tv/%s/59304c407a15bea99612bb69b0812dc9/%s"

####################################################################################################

def Start():

	# Make this plugin show up in the 'Video' section
	Plugin.AddPrefixHandler(VIDEO_PREFIX, VideoMainMenu, NAME, APP_ICON, ART)

	Plugin.AddViewGroup("InfoList", viewMode="InfoList", mediaType="items")
	Plugin.AddViewGroup("List", viewMode="List", mediaType="items")
	Plugin.AddViewGroup('PanelStream', viewMode='PanelStream', mediaType='items')
	Plugin.AddViewGroup('MediaPreview', viewMode='MediaPreview', mediaType='items')

	# Set some defaults
	MediaContainer.title1 = NAME
	MediaContainer.viewGroup = "InfoList"
	MediaContainer.art = R(ART)
	MediaContainer.userAgent = USER_AGENT
	
	ObjectContainer.art=R(ART)
	ObjectContainer.user_agent = USER_AGENT

	DirectoryItem.thumb = R(APP_ICON)
	VideoItem.thumb = R(APP_ICON)
	
	#DirectoryObject.thumb = R(APP_ICON)
	#VideoClipObject.thumb = R(APP_ICON)
	
	HTTP.CacheTime = CACHE_1HOUR
	HTTP.Headers['User-agent'] = USER_AGENT
	HTTP.Headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
	HTTP.Headers['Accept-Encoding'] = '*gzip, deflate'
	HTTP.Headers['Connection'] = 'keep-alive'
	
	Thread.Create(CheckAdditionalSources, sources=['lmwt','icefilms'])

####################################################################################################
# see:
#  http://dev.plexapp.com/docs/Functions.html#ValidatePrefs

def ValidatePrefs():

	if not Prefs['username'] or not Prefs['password']:
		return MessageContainer("Error", "No login information entered.")
	
	status = callTrakt(
		'account/test',
		None, 
		{'username' : Prefs['username'] , 'password' : Hash.SHA1(Prefs['password'])}
	)
	Log(status)	
	if (status == False):
		return MessageContainer("Error", "Invalid login information entered.")
		

	
####################################################################################################
# Main navigtion menu

def VideoMainMenu():

	oc = ObjectContainer(no_cache=True, title1=L("Video Channels"), title2=NAME, view_group="InfoList")
	
	oc.add(
		DirectoryObject(
			key=Callback(WatchlistMenu, type="movies", parent_name=oc.title2),
			title="WatchList",
			art = R(ART)	
		)
	)

	oc.add(
		PrefsObject(
			title=L("PrefsTitle"),
			tagline=L("PrefsSubtitle"),
			summary=L("PrefsSummary"),
		)
	)
	
	return oc
	
####################################################################################################
# Menu users seen when they select TV shows in Main menu

def WatchlistMenu(type=None, genre=None, path=[], parent_name=None):

	oc = ObjectContainer(no_cache=True, title1=parent_name, title2="WatchList", view_group="InfoList")

	watchlist = callTrakt(
		"user/watchlist/shows.json",
		[Prefs['username']], 
		{ 'username': Prefs['username'], 'password':Hash.SHA1(Prefs['password']) },
	)
	
	Log(watchlist)
	
	for item in watchlist:
	
		oc.add(
			DirectoryObject(
				key=Callback(
					SeasonsMenu,
					imdb_id=item['imdb_id'],
					show_name=item['title'],
					tvdb_id=item['tvdb_id'],
					art=item['images']['fanart'],
					name=item['title'],
					parent_name=oc.title2,
				),
				title=item['title'],
				summary=item['overview'],
				thumb=item['images']['poster'],
				art=item['images']['fanart'],
			)
		)
		
	return oc


####################################################################################################

def SeasonsMenu(imdb_id=None, show_name=None, tvdb_id=None,art=None, name=None, parent_name=None):
	
	oc = ObjectContainer(no_cache=True, title1=parent_name, title2=name, view_group="InfoList")

	seasons = callTrakt(
		"show/seasons.json",
		[tvdb_id],
		None
	)
	
	for season in sorted(seasons, key=lambda x: x['season']):
		Log(season)
		oc.add(
			DirectoryObject(
				key=Callback(
					EpisodesMenu,
					imdb_id=imdb_id,
					show_name=show_name,
					tvdb_id=tvdb_id,
					season=season['season'],
					name="Season " + str(season['season']),
					parent_name=oc.title2,
					art=art,
				),
				title="Season " + str(season['season']),
				thumb=season['images']['poster'],
				art=art,
			)
		)
	return oc


####################################################################################################

def EpisodesMenu(imdb_id=None, show_name=None, tvdb_id=None,season=None, art=None, name=None, parent_name=None):
	
	oc = ObjectContainer(no_cache=True, title1=parent_name, title2=name, view_group="InfoList")

	episodes = callTrakt(
		"show/season.json",
		[tvdb_id,season],
		None
	)

	for episode in episodes:
	
		oc.add(
			DirectoryObject(
				key=Callback(
					SourcesMenu,
					imdb_id=imdb_id,
					show_name=show_name,
					tvdb_id=tvdb_id,
					season=season,
					episode=episode['number'],
					art=art,
				),
				title="Episode " + str(episode['number']) + " - " + episode['title'],
				summary=episode['overview'],
				thumb=episode['images']['screen'],
				art=art,
			)
		)
	return oc

####################################################################################################
# SOURCES MENUS
####################################################################################################
def SourcesMenu(imdb_id=None, show_name=None, tvdb_id=None, season=None, episode=None, art=None, name=None, parent_name=None):
	
	oc = ObjectContainer(no_cache=True, title1=parent_name, title2=name, view_group="InfoList")

	for source in Dict[ADDITIONAL_SOURCES_KEY]:
	
		oc.add(
			DirectoryObject(
				key=Callback(
					SourcesAdditionalMenu,
					imdb_id=imdb_id,
					show_name=show_name,
					tvdb_id=tvdb_id,
					season=season,
					episode=episode,
					source=source
				),
				title=source,
				art=art
			)
		)
	return oc
	
	
####################################################################################################
def SourcesAdditionalMenu(imdb_id=None, show_name=None, tvdb_id=None, source=None, season=None, episode=None, art=None, name=None, parent_name=None):

	Log(source)
	# See which additional sources are available.	
	url = "http://localhost:32400/video/" + source + "/sources/" + imdb_id
	
	url += "/" + urllib.quote(show_name) + "/" + str(season) + "/" + str(episode)
	
	Log(url)
	
	# Can't use Redirect as it doesn't seem to be supported by some clients <sigh>
	# So get the data for them instead by manually doing the redirect ourselves.
	request = urllib2.Request(url)
	request.add_header('Referer', "http://localhost:32400" + VIDEO_PREFIX + "/")
	return urllib2.urlopen(request).read()
	
####################################################################################################
	
def PlayVideoNotSupported(mediainfo):

	return ObjectContainer(
		header='Provider is either not currently supported or has been disabled in preferences...',
		message='',
	)

####################################################################################################
#
@route(VIDEO_PREFIX + '/mediainfo/{url}')
def MediaInfoLookup(url):

	"""
	Returns the media info stored in the recently browsed item list
	for the given provider URL or None if the item isn't found in the
	recently browsed item list.
	"""
	
	# Get clean copy of URL user has played.
	decoded_url = String.Decode(str(url))
	#Log(decoded_url)
	
	# See if the URL being played is on our recently browsed list.
	item = cerealizer.loads(Data.Load(BROWSED_ITEMS_KEY)).getByURL(decoded_url)

	if (item is None):
		Log("****** ERROR: Watching Item which hasn't been browsed to")
		return ""
	
	# Return the media info that was stored in the recently browsed item.
	return demjson.encode(item[0])


def callTrakt(action, params=None, values=None):

	if (params is None):
		end_params = ""
	else:
		end_params = "/".join([str(x) for x in params])
		
	data_url = TRAKT_URL % (action, end_params)
	Log(data_url)
	try:
		response = HTTP.Request(data_url, data=JSON.StringFromObject(values))
		result = JSON.ObjectFromString(response.content)		
		Log(response.content)
		Log(result)
		
		return result
		
	except Exception, ex:
		Log.Exception(".....")
		return False
		
        
####################################################################################################
# LMWT Plugin specific helper methods.

####################################################################################################

@route(VIDEO_PREFIX + '/playback/external/{id}')
@route(VIDEO_PREFIX + '/playback/external/{id}/{season_num}/{ep_num}')
def PlaybackStartedExternal(id, season_num=None, ep_num=None):

	return ""

####################################################################################################

def PlaybackMarkWatched(mediainfo, path):
	
	return ""

####################################################################################################
def CheckAdditionalSources(sources):

	"""
	Check which of the additional sources this plugin knows about are
	actually available on this machine.
	"""

	Dict[ADDITIONAL_SOURCES_KEY] = []
	
	for source in sources:
		try:
			# Create the dummy URL that services register themselves under.
			pluginURL = "http://providerinfo.%s/" % source
			Log(pluginURL)
			Log(URLService.ServiceIdentifierForURL(pluginURL))
			# Query plex to see if there is a service to handle the URL.
			if (
				URLService.ServiceIdentifierForURL(pluginURL) is not None and
				'sources=true' in URLService.NormalizeURL(pluginURL)
			): 
				Dict[ADDITIONAL_SOURCES_KEY].append(source)
		except Exception, ex:
			Log.Exception("Error working out what additional sources are available.")
			pass

	