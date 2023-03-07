'''
This script is used for analyzing YouTube comments written by certain users
who you suspect of trolling or astroturfing.
Works on YouTube videos with unrolled comments,
saved to a local folder as HTML. You just add a "users.txt" file with
a list of suspect usernames to the same folder, then launch the script.

It will do several things with these users' comments:

1. Saves them to a single large text file, to make it easier
   to search for specific words.
2. Saves a list of all links within these comments, grouped by
   their domains.
3. Uses Graphviz (if available) to visualize these outgoing links
   and puts the resulting SVG file in a separate folder

I created it while preparing a blog post (in Polish).
It was used to explore some coordinated networks promoting the interests
of large agrochemical corporations, including Monsanto.

However, if you provide your own lists of usernames and (optionally) styling
rules, you should be able to adapt it to your purposes, as long as you stick
to YouTube comments. More details at the end of this file.

This pile of spaghetti code was brought to you by:
ciemnastrona.com.pl
A blog about corporate scandals and protecting your privacy
'''

__author__ = 'Bob Adook'
__license__ = 'MIT'

# ^ In short: just use it however you want ;) No strings attached.
# However, I take no responsibility for anything you do.

import re
import json

from pathlib import Path
from subprocess import Popen
from logging import error, warning, exception
from urllib.parse import urlparse, quote
from textwrap import wrap
from shutil import which
from sys import modules
from collections import Counter
from hashlib import md5

RUNS_IN_IDLE = ('idlelib' in modules)

##################
# External modules
##################

# Beautiful Soup
BeautifulSoup, NavigableString, FeatureNotFound = None, None, None

try: from bs4 import BeautifulSoup, NavigableString, FeatureNotFound
except Exception: error('Failed to import the BeautifulSoup package! '
                        'To install it, open your console and type:\n\n'
                        'pip install beautifulsoup4\nand then:\n'
                        'pip install lxml\n')

# LXML
if BeautifulSoup and FeatureNotFound:
    try:
        _ = BeautifulSoup( 'test', 'lxml' )
    except FeatureNotFound:
        error('[ERROR] No LXML library, impossible to read website content. '
              'Open your console and type:\n'
              'pip install lxml\n')
        BeautifulSoup = None

# emoji
UNICODE_EMOJI = []
try: from emoji import UNICODE_EMOJI
except Exception:
    error('Failed to import the "emoji" packages, emojis will not be shown '
          'within the comments. To install it, open your console and type:\n'
          'pip install emoji\n')

# dot
DOT = which('dot')
if not DOT:
    error('No external "dot" program, impossible to create a graph of links. '
          'A file in GV format will still be created, but you will have to '
          'give it to Graphviz or a similar program.\n'
          'You can install "dot" by following the instructions from:\n'
          'http://www.graphviz.org/download/\n') 

MODULES_OK = BeautifulSoup

###################################
# Defaults, do not change them here
# (only at the end of the script)
###################################

SPECIAL_USERS = []
SPECIAL_USER_STYLING = {}
SPECIAL_USER_HASHES = set()
WEBSITES_TO_CLUSTERS = {}
STARTING_CLUSTER = 'youtube'
RESULT_FOLDER = 'TextSummaries'

#################################################
# Configurable defaults, you can change them here
#################################################

MAX_NODE_LINE_LENGTH = 25
MAX_NODES_IN_COLUMN = 15
BASE_EDGE_WIDTH = 2
MINIMIZE_EDGE_NUMBER = False #If True, 1 edge = 1 comment
GRAPH_ENGINES = ['dot'] # By default "dot" only, but you can try "neato" etc.

#################################################
# Catching YouTube comments from suspected trolls
#################################################

def _is_user_from_special_list( author ):
    '''
    Checks if a comment's author is among suspected troll accounts.
    Caches username hashes to avoid costly computations.
    '''
    is_special,namehash = False,None
    namehash = hash_username( author )
    if namehash in SPECIAL_USER_HASHES or namehash in SPECIAL_USER_STYLING:
        is_special = True

    return is_special, namehash


TROLL_RE = None

def find_troll_name_in_text( comment_body ):
    '''
    Sometimes troll comments get deleted, but references to their names
    still stay inside the text. This function finds such comments.

    TODO: this is currently unused; would have to be added right after the
    "is_troll_comment" checked, for the Else... case.
    '''
    if not TROLL_RE:
        # Make regex for finding non-mention usernames in text
        re.compile( '[^@]({})'.format( '|'.join( SPECIAL_USERS )))
        
    trolls = TROLL_RE.search( comment_body.text )
    if trolls: trolls = list( trolls.groups() )
    return trolls

######################################
# General YouTube comment text parsing
######################################

def _get_links_in_yt_comment_body( body ):
    tag_attrs = {'class':'yt-simple-endpoint'}
    return [l.text.strip() for l in body.find_all('a', attrs=tag_attrs)]


def has_link_parent( elem: NavigableString ):
    '''
    Checks if a string of text nested deeper within elements has a
    link container as a parent and thus is also a link.
    '''
    for p in elem.parents:
        if p.name == 'a':
            return True
    return False


def gather_nested_text( textbox ):
    '''
    Parses nested text of troll comments on YouTube
    '''        
    encountered_link = False
    chunks = []
    for elem in textbox.descendants:

        # Setting general helpful flags
        if elem.name == 'a': encountered_link = True

        # Tag-specific actions
        if elem.name == 'img':
            try: alt_text = elem.attrs["alt"]
            except KeyError: alt_text = ''

            if not alt_text: text = '[IMAGE]'
            elif alt_text in UNICODE_EMOJI: text = alt_text
            else: text = f'[IMAGE: "{alt_text}"]'
                
            chunks.append(('I',text))
            
        elif type(elem) == NavigableString:

            if not encountered_link:
                chunks.append(('T', str(elem)))
            elif encountered_link:
                is_link = has_link_parent( elem )
                if is_link: chunks.append(('L', str(elem)))
                else: chunks.append(('T', str(elem)))

    text = ' '.join( text for _,text in chunks )                                   
    return text


def parse_youtube_comment( comment ):
    '''Initially parses a YouTube comment, extracting author, link and text'''

    # Replace all relative links with absolute ones
    for l in comment.find_all(True, attrs={'href':True}):
        link = l.attrs['href'] 
        if link.startswith('/'): l.attrs['href'] = 'www.youtube.com'+link

    author_box = comment.find( 'a', attrs={'id':'author-text'} )
    author = author_box.text.strip()

    linkbox = comment.find(True, attrs={'class':'published-time-text'})
    comment_link = linkbox.find('a').attrs['href']

    textbox = comment.find(True, attrs={'id':'content-text'})
    text = gather_nested_text( textbox )
    text = re.sub('(\s)\s+', '\g<1>', text)

    return [author, None, comment_link, text, None] #Nones for hash and links

##########################
# Some name anonymizations
##########################

HASHED_NAMES = {}

def hash_username( username ):
    if not username: return ''
    try: name_hash = HASHED_NAMES[ username ]
    except KeyError:
        hasher = md5()
        hasher.update( bytes(username,'utf-8') )
        name_hash = hasher.hexdigest()
        HASHED_NAMES[ username ] = name_hash

    return name_hash


def _replace_with_anonymous_id( text, user_name, user_map ):
    '''
    Gets a number corresponding to the user's name and replaces
    all occurrences of the name with a number.
    '''
    try: user_i = user_map[ user_name ]
    except KeyError:
        user_i = len(user_map)
        user_map[ user_name ] = user_i
    
    new_text = text.replace( user_name, f'[USER {user_i}]' )
    return new_text, user_i


def anonymize_mention( user_mention, text, user_map ):
    '''Anonymizes user mentions within the comment's body'''
    user_name = user_mention.lstrip('@')
    firstname = user_name.split(' ')[0]

    new_text, user_i = _replace_with_anonymous_id( text, user_name, user_map )
    
    if firstname != user_name:
        new_text = new_text.replace( firstname, f'[USER {user_i} NAME]' )

    return new_text
            
ANON_NAMESET = set()

def anonymize_names( usr_mentions, author_re, com_data, user_map ):
    '''
    Anonymizes all the names found within a comment, both in link
    mentions and references to other users in the text itself.
    Note: might remove too much if users choose common words as their names.
    For this reason, you can provide your custom ignore lists.
    '''

    # First, replace active mentions given as links
    text = com_data[3]
    for user_mention in usr_mentions:
        text = anonymize_mention( user_mention, text, user_map )

    # Then replace non-link references (to old/inactive usernames)
    text = text.strip()
    if text.startswith('+') or text.startswith('@'):
        user_name = text.split('\n')[0]
        text, user_i = _replace_with_anonymous_id( text, user_name, user_map )

    # Finally, use regex to replace in-text references to other users
    if author_re:
        names = author_re.findall( text )
        ANON_NAMESET.update( names ) #For debugging purposes
        for name in sorted( names, reverse=True ): # Start from longest
            text, _ = _replace_with_anonymous_id( text, name, user_map )

    com_data[3] = text

######################
# Saving info to files
######################

def _save_to_textfile( data, filename ):
    '''
    A generic function to bundle all other ones and save text files
    to a separate folder.
    '''
    outfolder = Path( RESULT_FOLDER )
    if not outfolder.exists(): outfolder.mkdir()
    outpath = outfolder / filename
    with open( outpath, 'w',  encoding='utf-8') as out:
        out.write( data )


def _save_website_data( website_data ):
    '''Saves YouTube video names and the links leading to them'''

    links = [d[2] for d in website_data]
    _save_to_textfile( '\n'.join(links), 'website_links.txt' )
    
    names = [d[1] for d in website_data]
    _save_to_textfile( '\n'.join(names), 'websites.txt' )
    

def _save_comments( trolls_by_website ):
    '''
    Formats the comments from under all collected videos
    and saves them to a single large text file.
    Useful for finding certain words and phrases later on.
    '''
    textlines = []
    for website, comments in trolls_by_website.items():
        textlines.append(f'\n\n### {website} ###\n\n')
        for i, com_data in enumerate(comments):
            author, ahash, comment_link, text, links = com_data
            anon_name,_ = SPECIAL_USER_STYLING[ ahash ]
            
            com_as_text = (f'====\n{i}\n'
                           f'{anon_name}\n{comment_link}\n---\n'
                           f'{text}\n')
            textlines.append( com_as_text )

    _save_to_textfile( '\n'.join( textlines ), 'comments.txt' )


def _get_url_counts( connections ):
    '''
    Counts the websites which suspected comments are linking to
    and groups them by domains (e.g. youtube.com)
    '''
    destinations = [dest for _,dest,_,_ in connections]
    counts = sorted( list( Counter( destinations ).items()),
                     key=lambda x: x[1] ) # By number
    
    counts_by_domain = {}
    for url_info, num in counts:
        url, domain = url_info
        try: counts_by_domain[ domain ].append( (url,num) )
        except KeyError: counts_by_domain[ domain ] = [(url,num)]
    
    return counts_by_domain


def _save_url_counts( url_count_by_domain ):
    
    textlines = []
    for domain, url_counts in url_count_by_domain.items():
        total_count = sum(int(n) for _,n in url_counts)
        textlines.append(f'\n## {domain} ({total_count})\n')
        for url,num in url_counts:
            textlines.append( f'{url} ({num})' )

    _save_to_textfile( '\n'.join( textlines ), 'links.txt' )
    
 
##############################################
# Helper functions for adapting text and links
##############################################

def get_title_and_link( html ):
    '''Gets the link to the YouTube video under which comments were posted'''

    website_title, link = '',''
    
    # Get the link to the video by looking at comment links
    # (warning: may fail if comment text contains links to other
    # YouTube comments, though it rarely ever happens)
    
    links = (l for l in html.find_all( 'a', attrs={'href':True}))
    for l in links:
        url = l.attrs['href']
        if 'watch?v=' in url and '&lc=' in url:
            # Link to a specific comment; trim out comment parameter and
            # change relative path to an absolute one
            link = re.sub( '&lc=.*$', '', url)
            if link.startswith('/'): link = 'https://www.youtube.com' + link
            break

    if 'youtube' in link:
        try: website_title = html.find('title').string.strip()
        except AttributeError: pass
        
    return website_title, link


def _shorten_link( l ):
    '''
    Sometimes multiple links point to the same website. In order to avoid
    treating them as separate ones, we can trim them to their shortes form
    (no "www." in head or ".html" in tail etc.)
    '''
    # The order of transformations should not be changed,
    # because urlparse can't find domain
    # without the HTTP(-S) indicator (and we want to remove it)
    
    l = re.sub('www\.', '', l.lower())

    # Try various ways of getting the domain
    domain = urlparse(l).netloc
    if not domain:
        dom_start_re = re.search('^(.*?)/', l)
        if dom_start_re: domain = dom_start_re.group(1)
    else:
        dom_re = re.search('[^.]+\.[^.]+$', domain )
        if dom_re: domain = dom_re.group(0)
        
    l = re.sub('^https*://','', l)
    return l,domain
    

########################################
# Modules responsible for graph creation
########################################

def _escape_special_chars( text ):
        return re.sub('[^A-Za-z ]+','', text)


class GraphCreator:

    connections = []
    _node_codes = {}
    _current_node_num = 1

    HEAD = (
        '// Made using a script from ciemnastrona.com.pl.\n'
        '// You can modify the graph by making changes to this file,\n'
        '// then launching the console in the same folder and typing:\n\n'
        '// dot -T svg graph.gv -o graph.svg\n\n'
        '// (dot must be installed on your computer)')

    DEFAULT_GRAPH_PARAMS = {
        'edge': {'color': '#8caff3',
                 'penwidth':str(BASE_EDGE_WIDTH)},
        'node': {'color': '#4bc9c8', 'fontcolor':'#dddddd'},
        'graph': {
            'fontname': 'Helvetica',
            'bgcolor': '#252525',
            'ranksep': '2', 'nodesep': '1.2', 'rankdir': 'LR',
            'splines': 'line',
            'newrank': 'true',
            'overlap': 'prism'
            }
        }

    CIRCULAR_GRAPH_PARAMS = {
        'edge': {'color': '#8caff3',
                 'arrowsize':'0.4',
                 'penwidth':'2.0'},
        'node': {'color': '#4bc9c8', 'fontcolor':'#dddddd'},
        'graph': {
            'bgcolor': '#252525',
            'size': '7.75,10.25',
            'mindist': '0.1',
            'overlap': 'prism'
            }
        }

    DEFAULT_CLUSTER_TEMPLATE = (
        '  subgraph cluster_@@NAME@@ {\n\n'
        '    edge [style=invis];\n'
        '    ranksep=2;\n'
        '    @@NODES@@\n'
        '  }')

    cluster_map = None
    domains_to_clusters = None
    starting_cluster = None
    website_name_re = None

    SPECIAL_NODES = []

    GRAPH_TEMPLATE = None
    RENDERER = 'dot'
    GRAPH_FILE = 'graph.gv'

    def __init__( self, cluster_map=None, starting_cluster=None ):
        
        if self.RENDERER == 'twopi':
            self.SELECTED_ATTRS = self.CIRCULAR_GRAPH_ATTRS

        if starting_cluster:
            self.starting_cluster = starting_cluster

        # Converting dictionary-form params to Graphviz syntax
        top_level_attributes = []
        for category, params in self.DEFAULT_GRAPH_PARAMS.items():
            attributes = ', '.join( f'{k}="{v}"'
                                    for (k,v) in list(params.items()) )
            attributes = f'  {category} [{attributes}];'
            top_level_attributes.append( attributes )
        top_level_attributes = '\n'.join( top_level_attributes )

        # Regex for grouping domains into clusters
        if cluster_map:
            self.cluster_map = cluster_map
            self.domains_to_clusters = self._prepare_cluster_map( cluster_map )

            special_domains = list(cluster_map.keys())
            self.website_name_re = re.compile(
                '({})'.format('|'.join( special_domains )))
                  
        self.GRAPH_TEMPLATE = (
            f'{self.HEAD}\n'
            'digraph Connections {\n\n'
            f'{top_level_attributes}\n\n'
            '@@NODES@@\n\n'
            '@@CLUSTERS@@\n\n'
            '@@CONNS@@\n'
            '}')

    def _prepare_cluster_map( self, cluster_map ):
        '''
        Multiple domain names can lead to a single cluster. This function
        sets the first one as the whole cluster's name and the others
        as aliases.
        '''
        domain_to_cluster_map = {}
        for label in cluster_map.keys():
            variations = label.split('|')
            for name_var in variations:
                domain_to_cluster_map[ name_var ] = label
                
        return domain_to_cluster_map
       

    def _format_node( self, nodetext ):
        '''
        Formats the displayed text of a node by wrapping it. If it's
        one of the special nodes, it also sets its style attributes.
        '''
        nodetext = nodetext.replace('\n','\\n')
        try:
            node_num = self._node_codes[ nodetext ]
            label = ''
        except KeyError:
            node_num = self._current_node_num

        oneline_text = nodetext.replace('\\n','')
        lowtext = oneline_text.lower()

        match = self.website_name_re.search( lowtext )
        if match:
            fullname = self.domains_to_clusters[ match.group(1) ]
            styleinfo = WEBSITES_TO_CLUSTERS[ fullname ]
            styleinfo = ',style=filled,'+ styleinfo
        else:
            styleinfo = ''

        url_to_source = ''
        if '/' in lowtext:
            url = quote(lowtext)
            if not url.startswith('http'): url = 'https://'+url
            url_to_source = f', href="{url}"'
        
        graphviz_node = (f'{node_num} [label="{nodetext}", '
                         f'tooltip="{oneline_text}" {url_to_source}'
                         f'{styleinfo}]')
                         
        self._current_node_num += 1
        self._node_codes[ nodetext ] = node_num
            
        return node_num, graphviz_node


    def _format_link_for_display( self, link, short_domain=None ):
        '''Wraps the link so that its domain fits on the first line'''        
        short_link = '\n'.join( wrap( link, MAX_NODE_LINE_LENGTH )  )
        return short_link

    def _sort_by_influence( self, nodes, conn_num ):
        '''
        Puts nodes with the highest number of inbound connections
        at the start.
        '''
        return sorted( nodes,
                       key=lambda node: conn_num[ node[0] ],
                       reverse=True)

    def reorder_nodes_by_clusters(self, node_map, clusters, conn_num):
        '''Places clustered nodes in a grid'''

        normal_nodes, nodes_from_clusters = [],[]
        
        for clustname,nodes in clusters.items():
            unique_nodes = list(set(nodes))
            clusters[clustname] = unique_nodes[:]

            unique_nodes = [(node,clustname) for node in unique_nodes]
            unique_nodes = self._sort_by_influence( unique_nodes, conn_num )
            
            if clustname == 'nongrouped': normal_nodes = unique_nodes[:]
            else: nodes_from_clusters += unique_nodes

        ordered_nodes = normal_nodes + nodes_from_clusters
        return ordered_nodes

    def _join_columns( self, left_col, right_col, dummyname, dummy_num=1 ):
        '''
        Adds a new column to the left of the given one, joining them
        together with a dummy node acting as a nexus in the middle.
        '''

        dummy = dummyname
        
        gv_rows = []
        gv_rows.append( f'{dummy}[style=invis]' )
        gv_rows.append( 'edge[style=invis]' )
        for node in left_col:
            gv_rows.append( f'{node} -> {dummy}')

        prev_dummy = None
        if dummy_num > 1:
            for i in range(dummy_num):
                prev_dummy = dummy
                dummy = f'{dummyname}{i}'
                gv_rows.append( f'{dummy}[style=invis]' )
                gv_rows.append( f'{prev_dummy} -> {dummy}' )
                        
        for node in right_col:
            gv_rows.append( f'{dummy} -> {node}')
        gv_rows.append( 'edge[style=solid]' )
        
        gv_rows = '\n'.join( gv_rows )
        return gv_rows


    def place_nodes_in_grid( self, nodes_and_clusters, connections ):
        '''
        Places nodes into groups to set a limit on how many
        can placed in a single vertical column
        '''

        # Map nodes to either the main column or its left or right
        # If the node belongs to the same category as the main column,
        # but has no outgoing edges, it's moved to the left
        nodes_with_outbound_edges = set( n for n,_,_ in connections )

        nodes, starting_column, leftside_column = [], [], []
        for node, cluster in nodes_and_clusters:
            if cluster == self.starting_cluster:
                if node in nodes_with_outbound_edges:
                    starting_column.append( node )
                else: leftside_column.append( node )
            else:           
                nodes.append( node )

        # Grouping nodes into columns with a set max number of items
        node_groups, buffer, i = [], [], 0
        for n in nodes:
            buffer.append( n )
            if i == MAX_NODES_IN_COLUMN-1:
                node_groups.append( buffer[:] )
                buffer, i = [], 0
            else: i += 1
        if buffer: node_groups.append( buffer[:] )

        # Padding the last column with empty items
        first_group, last_group = node_groups[0], node_groups[-1]
        len_diff = len(first_group) - len(last_group)
        if len_diff > 0: last_group += (['']*len_diff)

        # Converting columns to rows joined with invisible arrows
        # since this is the format graphviz accepts
        groups_as_rows = list(zip(*node_groups))
        graphviz_lines = []
        for row in groups_as_rows:
            row = [str(n) for n in row if n != '']
            row = ' -> '.join( row )
            graphviz_lines.append( row )

        grid = '\n'.join(('', 'edge[style=invis]', '',
                          '\n'.join( graphviz_lines ),
                          '', 'edge[style=solid]', ''))

        # Joining the leftmost and main columns with the node grid
        # by placing invisible dummies between them
        left_c = ''
        if leftside_column:
            left_c = self._join_columns(
                leftside_column, starting_column, 'first_dummy' )
            
        main_c = ''
        if starting_column:
            main_c = self._join_columns(
                starting_column, first_group, 'dummy', dummy_num=4 )

        grid = '\n\n'.join( (left_c, main_c, grid) )
                    
        return grid, False

    def _make_clusters( self, cluster_data ):
        '''Converts node clusters to Graphviz syntax'''  
        
        clusters_as_text = []
        for c_name, c_nodes in cluster_data.items():
            c_nodes = list( set(c_nodes) )
 
            cluster_nodes, onerank = self._format_cluster_nodes( c_nodes )

            text_clust = self.DEFAULT_CLUSTER_TEMPLATE
            text_clust = text_clust.replace( '@@NAME@@', c_name )
            text_clust = text_clust.replace( '@@NODES@@', cluster_nodes )
    
            clusters_as_text.append( text_clust )
                          
        return '\n\n'.join( clusters_as_text )

    def _format_edges( self, connections ):
        '''Sets the color and width of graph edges'''

        if not MINIMIZE_EDGE_NUMBER:
            return [f'  {name1} -> {name2} [color="{c}"];'
                    for (name1, name2, c) in connections]
        
        conn_data = {}
        for data in connections:    
            try: conn_data[ data ] += 1
            except KeyError: conn_data[ data ] = 1

        edges = []
        for data, edge_num in conn_data.items():
            name1, name2, edgecolor = data
            attrs = []
            if edgecolor: attrs.append( f'color="{edgecolor}"' )
            if edge_num > 1:
                width = BASE_EDGE_WIDTH + edge_num*0.5
                attrs.append( f'penwidth={width}' )

            if attrs: attrs = ' [{}]'.format( '\n'.join(attrs) )
            else: attrs = ''
            
            edges.append( f'  {name1} -> {name2}{attrs};' )
                          
        return edges        

    def _make_graph_body( self ):
        '''
        Combines sources of information about nodes and goups them
        into clusters, determines colors of edges etc.
        '''
        node_map = {}
        url_map = {}
        connections = []
        clusters = {}
        clusterized_nodes = set()
        
        for (source_info, target_info, author, _) in self.connections:
            
            site1 = self._format_link_for_display( *source_info )
            site2 = self._format_link_for_display( *target_info )

            name1, new_node = self._format_node( site1 )
            if new_node: node_map[name1] = new_node 
            name2, new_node = self._format_node( site2 )
            if new_node: node_map[name2] = new_node

            url1, url2 = source_info[0], target_info[0]
            url_map[ name1 ] = url1
            url_map[ name2 ] = url2

            if author:
                _,edgecolor = SPECIAL_USER_STYLING[ author ]
            else:
                edgecolor = ''

            connections.append( (name1, name2, edgecolor) )
            
            # Map to clusters
            for s, slabel in ((site1, name1), (site2, name2)):
                for clustname in self.domains_to_clusters.keys():
                    if clustname in s.lower().replace('\n',''):
                        clustname = _escape_special_chars( clustname )
                        try: clusters[ clustname ].append( slabel )
                        except KeyError: clusters[ clustname ] = [slabel]
                        clusterized_nodes.add( slabel )

                # Experimental, make cluster for nongrouped
                if not slabel in clusterized_nodes:
                    try: clusters[ 'nongrouped' ].append( slabel )
                    except KeyError: clusters[ 'nongrouped' ] = [slabel]

        return node_map, url_map, connections, clusters


    def make_graph( self ):
        '''Adapts data to GV syntax and creates the content of graph file'''

        node_map, url_map, connections, clusters = self._make_graph_body()
        print('Creating a link graph...')

        # Get inbound connections number
        conn_num = Counter( c for _,c,_ in connections )
        conn_num = {n: num for n, num in conn_num.items() }
        for n in node_map:
            if not n in conn_num: conn_num[n] = 0

        reord = self.reorder_nodes_by_clusters
        ordered_nodes = reord( node_map, clusters, conn_num )
        grid_info,_ = self.place_nodes_in_grid( ordered_nodes, connections )
        
        node_info = '\n'.join( node_map[n] for n,_ in ordered_nodes )
        node_info = '\n\n'.join( (node_info, grid_info) )
        
        cluster_info = '\n'

        connections = self._format_edges( connections )
        connections = ('  edge[constraint=false];\n\n' #Prevent node shifting
                       + '\n'.join( connections ))

        graph = self.GRAPH_TEMPLATE
        graph = graph.replace( '@@NODES@@', node_info )
        graph = graph.replace( '@@CLUSTERS@@', cluster_info )
        graph = graph.replace( '@@CONNS@@', connections )
        
        self._save_graph_to_file( graph )


    def _save_graph_to_file( self, graph: str ):
        '''Saves graph to disk as both instructions (gv) and rendered SVG'''              

        outfolder = Path('LinkGraph')
        if not outfolder.exists(): outfolder.mkdir()

        outpath = outfolder / self.GRAPH_FILE
        with open( outpath, 'w', encoding='utf-8') as out:
            out.write( graph )

        for engine_name in GRAPH_ENGINES:
            eletter = engine_name[0]
            svg_outpath = outfolder / f'{eletter}graph.svg'
            args = [ engine_name, '-T', 'svg', outpath, '-o', svg_outpath ]
            try:                        
                gviz = Popen( args )
                gviz.wait()
            except Exception: continue
            if svg_outpath.exists():
                print('\n[SUCCESS]\n'
                      f'Created a link graph using "{engine_name}" and '
                      f'saved it to an SVG file:\n{svg_outpath.absolute()}')

                              
##########################################################
# Loading website content and getting data,
# either by parsing from scratch or grabbing a cached copy
##########################################################

CACHE_FOLDER, CACHE_FILE = Path('cached_content'), 'website_data.json'

def _get_prepared_data( json_file ):
    
    with open( json_file ) as j:
        data = json.load( j )
    print(f'Loaded data from {json_file}')
    return data


def _save_prepared_data( data ):
    
    folder = CACHE_FOLDER
    if not folder.exists(): folder.mkdir()
    json_file = folder / CACHE_FILE
    with open( json_file, 'w' ) as j:
        json.dump( data, j )


def get_website_data( html_files ):
    '''
    Gets all kinds of information available from a website: comments
    from specific trolls, links to external sources etc.
    '''
    json_file = CACHE_FOLDER / CACHE_FILE
    if json_file.exists():
        data = _get_prepared_data( json_file )
        return data
    
    print(f'Preparing HTML files from scratch...')
    user_map, data_container = {}, []
    for file in html_files:
        prepare_website_data( file, data_container, user_map )
    data = data_container
    
    _save_prepared_data( data )
    return data


def _prepare_anonymizer_regex( coms_with_authors ):
    '''
    Prepares a regex for anonymizing user names within the *text* of
    comments, which is then saved to a separate file.
    It is distinct from the anonymization of comment authors' names
    or user mentions ("@username" at comment start)
    '''
    authors = list(set( re.escape( a )
                        for _,a in coms_with_authors
                        if (len(a) > 2 and not a in ANON_EXCLUSIONS)))
    authors += ANON_INCLUSIONS

    if ANON_EXCLUSIONS:
        print( f'[ANONYMIZER] Excluding {len(ANON_EXCLUSIONS)} text strings '
               'from comment text anonymization')
    if ANON_INCLUSIONS:
        print( f'[ANONYMIZER] Forcing anonymization of {len(ANON_INCLUSIONS)} '
               ' text strings (potential names) within comment text')
    
    author_re = ''
    if authors:
        author_re = ('({})'.format('|'.join( authors )))     
        author_re = re.compile( r'\b' + author_re + r'\b', re.IGNORECASE)
        
    return author_re


def prepare_website_data( html_file, data_container, user_map ):
    '''Prepares website data from scratch'''

    print(f'Parsing {html_file}...')
    name = 'youtube'
    html = BeautifulSoup( open(html_file), 'lxml' )
    website, link = get_title_and_link( html )
    
    links_from_main_page = []
    troll_comments = []
    refs_to_trolls = []
   
    comments = html.find_all('ytd-comment-renderer')
    if not comments:
        error(f'No comments found in {html_file}! '
              'Perhaps it is not a YouTube video or YT changed its format')
        return

    coms_with_authors = []
    for com in comments:
        name_field = com.find('a', attrs={'id':'author-text'})
        author = name_field.text.strip()
        coms_with_authors.append( (com, author) )

    author_re = _prepare_anonymizer_regex( coms_with_authors )
        
    for com, author in coms_with_authors:
        
        is_from_list, namehash = _is_user_from_special_list( author )
        if not is_from_list: continue
        
        # All the actions below apply only to comments by suspected trolls

        com_data = parse_youtube_comment( com )
        com_data[1] = namehash #Hash instead of link
        
        body = com.find('div', attrs={'id':'content'} )
        com_links = _get_links_in_yt_comment_body( body )

        usr_mentions, outbound_links = [], []
        for cl in com_links:
            if not cl.startswith('@'): outbound_links.append( cl )
            else: usr_mentions.append( cl )

        anonymize_names( usr_mentions, author_re, com_data, user_map )
            
        com_data[-1] = outbound_links
        troll_comments.append( com_data )

    if not troll_comments:
        print('[WARN] No comments by suspect users found in:', html_file ) 

    site_data = (name, website, link, links_from_main_page,
                 troll_comments, refs_to_trolls)
    data_container.append( site_data )


def get_links_and_comments( data, usernames ):
    '''
    Gets outbound links for a given website, both from the main page
    content and from individual troll comments.
    '''
    connections, website_links = list(), set()
    troll_map = {}

    trolls_by_name = {}
    
    for website_data in data:
        
        (name, website, link, main_links,
         troll_comments, troll_name_mentions) =  website_data

        if not website: website = link

        # Skip duplicates
        link = link.rstrip('/') 
        link = link.replace('.html', '')
        if link in website_links:
            if not urlparse(link).path: pass #Just the domain, let it be
            else:
                warning(f'Found duplicate of {link}, skipping')
                continue
        else: website_links.add( link )

        # Handle outbound links from main website content
        for l in main_links:
            if re.search('(\.png|\.jpg)$', l): continue # Skip images
            
            l = l.rstrip('/')
            l = l.replace('.html', '')
            l,domain = _shorten_link( l )
            conn_info = ((website, None), (l,domain), None, name)
            connections.append( conn_info )

        # Handle suspected troll comments
        for com_data in troll_comments:
            
            name,ahash,_,_,troll_links = com_data

            try: trolls_by_name[name] += 1
            except KeyError: trolls_by_name[name] = 1
                   
            try: troll_map[ website ].append( com_data )
            except KeyError: troll_map[ website ] = [ com_data ]
            
            for l in troll_links:
                if not '.' in l or not '/' in l: continue #Skip fake links
                l,domain = _shorten_link( l )
                conn_info = ((website,None), (l,domain), ahash, None)
                connections.append( conn_info )

    print('Number of comments made by suspected trolls:', trolls_by_name)
    
    troll_comments = troll_map
    return connections, troll_comments

########################
# Accepting custom lists
########################

def load_user_list( filename ):
    '''
    A general function for loading username lists, where each name
    occupies a single line of text. Used for troll-finding and name
    anonymization so far
    '''
    users = Path( filename )
    if not users.exists(): return []
    
    with open( users ) as u:
        usernames = [l for l in u.read().split('\n') if l]

    return usernames


def load_potential_troll_list():

    troll_file = 'users.txt'
                 
    if not Path( troll_file ).exists():
        error('[ERROR] No list of suspected troll account names found '
              'in the active folder'
              f'\n( {Path().absolute()} )\n\n'
              f'[SOLUTION] Create a file called "{troll_file}" within this '
              'folder. Each line should contain a single username.\n')
        return
    
    return load_user_list( troll_file )


def set_special_names_and_hashes( usernames ):
    '''
    Creates a script-wide list of usernames and hashes to be used
    for detecting troll comments and mentions of their names
    '''
    for uname in usernames:
        SPECIAL_USERS.append( uname )
        namehash = hash_username( uname )
        SPECIAL_USER_HASHES.add( namehash )

    print(f'[INFO] Loaded a list of {len(usernames)} suspected usernames')

########################
# Highest-level function
########################

def analyze_all_websites_in_folder( usernames, **graph_args ):
    '''
    Looks at all websites within the folder and graphs connections
    between them and external sources.

    :param usernames: list of usernames suspected of being trolls
    '''
    html_files = [p for p in Path().iterdir() if p.suffix == '.html']
    if not html_files:
        error('No files with the .html extension found in the active folder'
              f'\n( {Path().absolute()} )\n')
        return
  
    data = get_website_data( html_files )
    if not data:
        error('Failed to get any data from websites inside the active folder'
              f'\n( {Path().absolute()} )\n'
              'Perhaps YouTube changed the format of its websites or there '
              'is a bug within this script?')
        return

    print('\n[SUCCESS]\nLoaded all data for the saved YT videos '
          f'({len(data)})\n')
    _save_website_data( data )
          
    connections, troll_comments = get_links_and_comments( data, usernames )
    
    _save_comments( troll_comments )

    if not connections:
        print(f'[WARNING] No links found inside comments, so a link graph '
              'and their summary will not be created')
        return

    graph_maker = GraphCreator( **graph_args )
    graph_maker.connections = connections[:]
    graph_maker.make_graph()
    
    url_counts = _get_url_counts( graph_maker.connections )
    _save_url_counts( url_counts )

 
if __name__ == '__main__':

    # You can customize the items below if you wish,
    # they're currently specific to the blog post by Ciemna Strona

    ### INSTRUCTIONS
                  
    # First, you have to download some YouTube websites as HTML
    # (with all comments unrolled if possible) and place them
    # within the active folder.
                  
    # Then, place a file called "users.txt" in the same folder. Each line
    # should contain a full username of a suspected troll account.
    # Then launch the script.

    ### VARIABLES TO CUSTOMIZE
    
    # Below: a mapping of username MD5 hashes to their short names (used for
    # anonymization) and the color their links will have on the graph.
    
    SPECIAL_USER_STYLING = {
        '98f9ede02a07db6f8dd00f2e353425e5': ('Popeye', '#ff3838'),
        'f355412e8b732753092138c24e617d18': ('David', '#ffd954'),
        '3364ba675ce232d4b03e50d00f6492fc': ('Duke', '#7aebf2'),
        '9a4da08a4dcdaba6443da1c945faf54b': ('dsn...', 'yellow'),
        '7a3f555fc2bd434044328f00b53b73d5': ('River', 'green'),
        'aa6aa6b289cd1a84fe455a304c2c3fac': ('Uyop', '#db6ae8'),
        'b0eadcafa7b709e6770e960d0c25fe03': ('Peer', '#c44ee6' )
        }

    # Below: a mapping for special websites. Links which contain
    # the given text (keys) are placed close to each other
    # on the graph and given a distinct appearance (node color).
    # You can assign multiple domains to the same key by
    # separating them with a vertical bar (|). The text before the first bar
    # will be treated as the cluster's name
                  
    WEBSITES_TO_CLUSTERS = {
        'geneticliteracyproject': 'color="#8caff3",fontcolor=black',
        'youtube|youtu.be': 'color=red,fontcolor=black',
        'polityka': 'color=green,fontcolor=black',
        'risk-monger': 'color="#eab87d",fontcolor=black',
        'allianceforscience': 'color="#7de1ea",fontcolor=black',
        'gmoanswers': 'color="#b94ba8",fontcolor=black',
        'biofortified': 'color="#7dea7f",fontcolor=black',
        'monsanto.com|monsantoblog.eu': 'color="#64045e",fontcolor=white',
        'academicsreview': 'color="#41a648",fontcolor=white',
        'acsh': 'color="#763752",fontcolor=white'
        }


    # Below: lists of names to exclude from comment-text anonymization,
    # usually when they are not only usernames, but common words as well.
    # However, reference link anonymization ("@username"...) still applies.
    # Inclusions work the other way, by forcing replacement of strings.

    # You can add your custom exclusions by creating a file called
    # "do_not_anonymize.txt" in the same folder, with one text string per line.
    # You can also force some text strings (e.g. people's names) to always
    # be anonymized, by adding them to a file called "do_anonymize.txt"

    ANON_EXCLUSIONS = load_user_list( 'do_not_anonymize.txt' )
    ANON_INCLUSIONS = load_user_list( 'do_anonymize.txt' )


    ## Main functions below, DO NOT CHANGE THEM
    
    suspected_usernames = load_potential_troll_list()
    
    if MODULES_OK and suspected_usernames:
        set_special_names_and_hashes( suspected_usernames )
        analyze_all_websites_in_folder( suspected_usernames,
                                        cluster_map=WEBSITES_TO_CLUSTERS,
                                        starting_cluster=STARTING_CLUSTER)
    if not RUNS_IN_IDLE:
        print('')
        input('[Press Enter to quit]')
