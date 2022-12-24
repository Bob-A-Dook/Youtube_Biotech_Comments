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

At this point, it would be a bit painful, but possible.

You'd have to visit all YouTube videos listed in `websites.txt`, unroll all comments, and save them as HTML files. Then, you can extract comments by certain users and compare them to my list.

However, I will add my Python script as soon as possible. It makes the task much easier, as all that's needed is to gather the websites in a single folder. I will not provide them here, since they contain many unrelated comments.

**I give you permission to use the results of my research in any way you want. If you want to provide attribution, please link to this repository**.
