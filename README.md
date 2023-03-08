# Youtube Biotech CIB

This repo contains data from my hobby research on suspected [coordinated inauthentic behavior](https://www.logically.ai/resources/blog/what-is-coordinated-inauthentic-behavior) (CIB) within YouTube comments.

A small group of accounts is unusually active in defending the interests and products of large agrichemical corporations, mainly Monsanto (which, as they claim, “does not exist anymore”). They often resort to personal insults and copy-pasted responses.

## Highlights

I have researched a total of five English-speaking commenters from YouTube and one Polish-speaking commenter from a single video. 

There are three particularly active commenters who seem to know each other and often visit comment sections together. In total, **they have written almost 3500 comments across 34 analyzed videos**.

Many of their comments include *ad personam* attacks, denigrating remarks and other forms of abuse against people who distrust the agrichemical business (regardless of the merit of the critique itself). 

The commenters also post numerous links to Genetic Literacy Project, which has been proven to have strong ties to the biochemical industry, and to other industry-supporting websites.

## Contents

* `websites.txt` contains the names of YouTube videos I got the comments from.
* `comments.txt` contains a human-readable list of all comments written by the analyzed users.
* `links.txt` contains links outbound links from comments to other websites. They are grouped by domains and their number is given in brackets.
* `link-graph.svg` is a visualization of outgoing links. Each ellipse is a website and each edge of the graph is a single link. Edge colors are used to denote different comment authors.
* `graph.gv` is the raw Graphviz file. You can edit it if you want to change something about the presentation. Then use Dot (requires installing [Graphviz](https://graphviz.org/) to make a graph out of it.

The folder called `pl` also contains the exact same data, but for a single commenter from a single Polish YouTube video.

## Fair use and disclaimers

* This project was created only for personal research purposes.
* The comments contained here are only a small, non-substantial subset of all comments from the videos (which I acknowledge as YouTube's property).
* Source links to every single comment are provided inside the file.
* The original comments have been transformed into plaintext form and their formatting was changed. Due to this, they are merely transformations of the original content.

I have also attempted to anonymize the names of YouTube users mentioned in the comments to the best of my ability. The names of the analyzed accounts have been shortened. 

**Warning:** Some comments contain profanities.

## How to replicate the results

On March 2023, I've added the Python script I used for analyzing the comments. To reproduce my results:

1. Install [Python](https://www.python.org/downloads/) from its official website.

   Make sure you tick the `Install PIP` option during installation.

2. Use PIP to install the BeautifulSoup library for Python.

   Do it by typing `pip install beautifulsoup4` in your console.

3. Download and install [Graphviz](https://www.graphviz.org/download/).

   This is optional, used for visualizing links between comments and websites.

4. Visit all YouTube videos listed in `websites.txt`, **unroll all comments**, and save all websites to a single folder as HTML files.

   **Important**: do not use `Ctrl+S` to save the website to disk; it wouldn't include any comments!  
   Instead, you can open the browser's developer tools (`Ctrl+Shift+I`), right-click the *<html>* tag at the top, select the *Copy outer HTML* option and then copy the text to a text file; save with the *.html* extension.

5. Place the Python script in the same folder as the downloaded videos and run it.

If all goes smoothly, two new folders will appear.

* `LinkGraph` contains the Graphviz source file and the resulting graph of outbound links.
* `TextSummaries` contains the full text of comments, a list of outbound links and some other info.

Note: although my script recognizes certain users, it does not contain their full YouTube usernames; only their anonymous hashes and short forms.

## Extending the script

If you want to, you can adapt my script to your needs and analyze comments from *youtube.com* written by other suspected users, not only the ones I checked.

To do so, create a file called `users.txt` (important!) in the same folder as all the YouTube sites you've downloaded. Inside this file, put the usernames you want to analyze, one per line.

Additional quick customization options are described at the end of the script. Of course, sky is the limit if you know some Python yourself!

**I give you permission to use my script and the results of my research in any way you want. If you want to provide attribution, please link to this repository**.
