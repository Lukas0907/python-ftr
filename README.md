
# python-ftr

Python *partial* (re-)implementation of Five-Filters extractor. Cleans up HTML and extract its content for comfortable reading.

A notable difference is that this python implementation will fetch the website configuration from a centralized repository. 



## Installation

```
pip install git+https://github.com/1flow/python-ftr@master#egg=ftr
```

If you are using it in a Django project, you can benefit from `cacheops` to avoid repetitive fetching of website configuration files. Install it this way:

```
pip install cacheops
```

And configure `cacheops` [as usual](https://github.com/Suor/django-cacheops).


## Configuration


### Environment

- `PYTHON_FTR_CACHE_TIMEOUT`: optional, in seconds, as an integer. The caching time of websites configuration files. Defaults to 3 days. Not used if cache is not available.
- `PYTHON_FTR_REPOSITORIES`: one or more URLs, separated by spaces. In case you need a space in the URL itself, urlencode() it (eg. `%2f`). Default values include 1flow repository and official Five-Filters repository (see below).



### Website configuration repositories

If there are more than one repository, they will be tried in turn.

They must give access to RAW config TXT format, else. There is partial test against failure on this side but beware, it's relatively weak.

Eg. to use the filters from [the 1flow official repository](https://github.com/1flow/ftr-site-config), we use the following URL: `https://raw.githubusercontent.com/1flow/ftr-site-config/master/`.

TODO: `file://` repository pattern implementation. As of now, this package always fetches configuration from the centralized repository. This is not always wanted if you have a local copy, but as the main benefit of FTR is mutualizing the configurations and enhancing then via the community, it still feels legit to try to download the latest one without needing you to update them.



## Usage

### Simple, wrapped usage

```python

from ftr import ftr_process

extracted = ftr_process('http://en.wikipedia.org/wiki/Christopher_Lloyd')

```

If the extraction worked, this will return a `ContentExtractor` instance with useful attributes, else `None` will be returned. Most common attributes are `title` (utf-8 string), `body` (utf-8 cleaned HTML), `date` (utf-8 string, see below), `authors` (list of utf-8 strings).


### Advanced usage

To be documented more, but simply look at the `ftr_process()` function, it wraps the underlying classes that are meant to be easily included in any type of code.



## Differences with FiveFilters PHP implementation

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

- enhance this documentation and make it more complete.
- implement a minimal caching solution when `cacheops` is not available. Without `cacheops`, the process will fetch the config everytime, and in most setups this is not acceptable for obvious slowlyness reasons. Currently, this project is used only in 1flow and `cacheops` is available. PRs welcome. A simple `memoize()` could do the trick for very basic needs.
- allow to customize the datetime parser from the calling level. This will merge both worlds, allowing the library to return parsed datetimes, and the calling code to provide a custom parser.
- eventually, bring back the full `autodetect_on_failure` features if someones needs it.



## License

GNU Affero GPL version 3.

