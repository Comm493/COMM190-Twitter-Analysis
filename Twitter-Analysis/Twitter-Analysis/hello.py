from flask import Flask, render_template, request, jsonify
import atexit
import cf_deployment_tracker
import os
import json
import twitter
import time
from watson_developer_cloud import PersonalityInsightsV3, ToneAnalyzerV3

# Emit Bluemix deployment event
cf_deployment_tracker.track()

# Register the "Flask" Application
app = Flask(__name__)

# On Bluemix, get the port number from the environment variable PORT
# When running this app on the local machine, default the port to 8080
port = int(os.getenv('PORT', 8080))
    
# Initialize the Twitter API
# which will allow to pull-in a set of tweets from specific users
api = twitter.Api(consumer_key='fe653UPMinFzN93aMlHbJ4a26',\
                    consumer_secret='0QIZxnxEj57cb7uQ7wXWUSWtT4KNIwWqN59plji0wDi3rdXUuf', \
                    access_token_key='137493607-HaNIdpZaJsQuS9J8biWP604KGvJm6bzrDIEXLMTb', \
                    access_token_secret='OGOa6qkFfd8kBjsgadNsUkTi96BlolExZD9DrlwvrUtLF')

# Initialize the Watson Personality Insights API
# which will allow the ability to send the tweets for analysis and 
# return the profile
personality_insights = PersonalityInsightsV3(
                            version='2016-10-20',
                            username='d8bd36e6-629d-48c8-835f-0c8d070f1495',
                            password='2XHAUcgAbx1g')

# Initialize the Watson Tone Analyzer API
# which will allow the ability to send the tweets for analysis and 
# return the tone scores
tone_analyzer = ToneAnalyzerV3(
                    version='2016-05-19',
                    username='66a1a056-1cac-4924-af83-23db99514e9b',
                    password='oUprjwUXlT3T')

# Home Route;
# Whenever the user visits comm190.mybluemix.net/ 
#   render the template stored at templates/user_data.html
@app.route('/')
def home():
    return render_template('user_data.html')

# Analyze Twitter Route;
# Whenever a POST request is made to /analyzer-twitter/
#   Get the handle, fetch the Twitter data, Analyzer w/ Watson, and 
#   return the data, JSON formatted. If an error occurs, return the JSON formatted
#   error. 
@app.route('/analyze-twitter/', methods=['POST'])
def analyze_twitter():
    # Grab Twitter Handle from Form Request
    handle = request.form['twitter_handle']

    # If there was no 'twitter_handle' submitted from the HTML file, return an error
    if handle is None:
        return json.dumps({'error': 'Twitter handle not defined'})

    # Check for Cache 
    if os.path.exists('cache/'+handle+'.json'):
        # IF the cache file exists, then read the expiry date
        with open('cache/'+handle+'.json', 'r') as infile:
            json_object = json.load(infile)

            # If the cache is not expired, return the file contents as data
            if json_object['expiry'] >= time.time():
                return jsonify(json_object['profile'])


    # Grab Statuses from Twitter API, based on handle
    statuses = api.GetUserTimeline(screen_name=handle, count=200)
    
    # If there are no Tweets, return an error
    if len(statuses) == 0:
        return json.dumps({'error': 'No Tweets were returned for that handle'})

    # Build out 'content_item' objects for each Tweet in the list
    content_items_list = []
    utterances_item_list = []

    # For every Tweet that was returned, build out the 'content_item' object;
    #   This is fully documented in the Bluemix documentation
    for status in statuses:
        content_item = {
            "language": "en",
            "id": status.id, 
            "content": status.text,
            "contenttype": "text/plain"
        }

        # Add the content item to the list
        content_items_list.append(content_item)
        
        # Add the first 50 to the 'utterances_item_list'
        if (len(utterances_item_list) < 50):
            utterance = {
                "text": status.text,
                "user": handle
            }
            utterances_item_list.append(utterance)

    # Retrieve the Personality Profile from Watson
    profile = personality_insights.profile(\
            json.dumps({"contentItems": content_items_list}),\
            content_type='application/json',\
            raw_scores=False,
            consumption_preferences=True)

    # Retrieve the Tone Analyzer items from Watson
    tones = tone_analyzer.tone_chat(utterances_item_list)

    # Combine the 'tones' and the 'profile' variables into a single object
    profile['tones'] = tones

    # Write to Cache File 
    expiry = time.time() + 60*60*6
    cache_object = {"expiry": expiry, "profile": profile}
    with open('cache/'+handle+'.json', 'w+') as outfile:
        json.dump(cache_object, outfile)

    # Return the combined data, as a JSON object
    return jsonify(profile)

# Shutdown the App upon exit
@atexit.register
def shutdown():
    if client:
        client.disconnect()

# Start the server running, based on the above configuration
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port, debug=True)
