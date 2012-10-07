//## File type detetion in JavaScript
//
// Not currently related to the real libmagic but that might be nice
// eventually.

var NAME_EXTENSIONS = {
    ".js": "application/javascript",
    ".py": "text/x-python",
    ".json": "application/json",
    ".txt": "text/plain",
    "README": "text/plain",
    ".sh": "application/x-sh",
    ".html": "text/html",
    ".css": "text/css",
    ".md": "text/plain",
    ".coffee": "text/x-coffeescript"
    //...
}

function guess_file_type(doc) {
    doc.mime_type = "application/octet-stream";
    if (doc.basename) {
	for (var i in NAME_EXTENSIONS) {
	    if (endswith(doc.basename, i)) {
		doc.mime_type = NAME_EXTENSIONS[i];
	    }
	}
    }
}

