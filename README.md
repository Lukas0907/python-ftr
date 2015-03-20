
# python-ftr


FTR is a *partial* (re-)implementation of the [Five-Filters extractor
](http://fivefilters.org/) in Python.

It cleans up HTML web pages and extract their content and metadata for a
more comfortable reading experience (or whatever you need it for). It uses
a centralized and mutualized repository of configuration files to parse
websites at the most precise level possible, and fallbacks to the well-known
`readability` automatic extractor if no configuration is found.

A notable difference is that this python implementation will fetch the
website configuration from a centralized repository on the internet on the
fly if no configuration is found locally.

[Full documentation is available](http://python-ftr.readthedocs.org).




## Differences with the FiveFilters PHP implementation

`python-ftr` :
- has only one parser library (`lxml`) for now. The `html5lib` has not been ported yet.
- does not convert date strings to `datetime` objects. I felt this more flexible to handle them at the upper level, giving access to custom datetime parsers. This is likely to change if I implement passing a custom parsing function to the extractor.
- uses [readability-lxml](https://github.com/buriy/python-readability) for cleaning after non-automatic body extraction. Even if it's a port of Arc90 `readability.js` like the [PHP Readability port](https://github.com/wallabag/wallabag/blob/master/inc/3rdparty/libraries/readability/Readability.php) used by Five Filters, it could **eventually** produce different results from it given the way they compute weight on contents (I didn't compare them code-wise). 
- **does not fallback to automatic parsing when no site config is available**, but it does partially when a config is found and fails. As `python-ftr` was created to be included in a complex parsing chain, we had no need for an automatic parsing *when there is no config for current site*. See below for details. 
- has no fingerprints support. This feature looked unfinished or at least not enough documented for me to understand it in the original code.
- does not use the `global` five-filters config file at all. The `.txt` looked unmaintained, and generic fallbacks can still be implemented outside of this module : you can provide your own global config via an argument when using the API.



## Automatic extraction

If you need fully-automatic parsing in no-config-found situations — which are easily detectable because `process()` and the low-level API raise `SiteConfigNotFound` — just use `readability-lxml`, `breadability`, `python-goose`, `soup-strainer` or whatever fits you. 

In the case of an **existing config but parsing failing** for whatever reason, we still honor `autodetect_on_failure` and try to extract at least a `title` and a `body` via `readability-lxml`.

This is not as featureful as the PHP implementation which tries to extract date, language and authors via other ways, but still better than nothing. 

When automatic extraction is used, the `ContentExtractor` instance will have a `.failures` attributes, listing exactly which non-automatic extraction(s) failed.

In the case where a config is found but it has no `site` or `body` directive (eg. automatic extraction should be explicitely used), the `.failures` attributes will not be set if automatic extraction worked. 



## TODO

See [issues wishlist](/1flow/python-ftr/labels/wishlist) for a dynamic todo list.



## License

GNU Affero GPL version 3.

