var base_path = "/";
var db_base = base_path + "db/";

function b64decode(b64data) {
    /* Nod to http://www.webtoolkit.info/javascript-base64.html */
    
    var keys = ("ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                + "abcdefghijklmnopqrstuvwxyz"
                + "0123456789+/");
    var output = [];
    var chr1, chr2, chr3;
    var enc1, enc2, enc3, enc4;
    var i = 0;
    var input = b64data.replace(/[^A-Za-z0-9\+\/]/g, "");
    while (i < input.length)
    {
        enc1 = keys.indexOf(input.charAt(i++));
        enc2 = keys.indexOf(input.charAt(i++));
        chr1 = (enc1 << 2) | (enc2 >> 4);
        output.push(chr1);
        if (input.length == i)
        {
            break;
        }
        enc3 = keys.indexOf(input.charAt(i++));
        chr2 = ((enc2 & 15) << 4) | (enc3 >> 2);
        output.push(chr2);
        if (input.length == i)
        {
            break;
        }
        enc4 = keys.indexOf(input.charAt(i++));	       
        chr3 = ((enc3 & 3) << 6) | enc4;
        output.push(chr3);
    }
    return output;
}

function hexdump(charcodes)
{
    var hex_result = [];
    var str_result = [];
    var result = [];
    var i;
    var flush = function()
    {
        var hex_part = hex_result.join(" ");
        var hex_part_padding =  ("                        "
                                 + "                        ");
        var hex_part = hex_part + hex_part_padding;
        var hex_part = hex_part.substr(0, hex_part_padding.length);
        var hex_part = (
            hex_part.substr(0, Math.floor(hex_part.length / 2)) + " " 
            + hex_part.substr(Math.floor(hex_part.length / 2), 
                              hex_part.length));
        var line_id = "00000000" + (i - str_result.length + 1).toString(16);
        var line_id = line_id.substring(line_id.length - 8);
        if (str_result.length > 0)
	    {
            result.push(line_id + "  " + hex_part + " |" 
                        + str_result.join("") + "|\r\n");
        }
        hex_result.splice(0, hex_result.length);
        str_result.splice(0, str_result.length);
    }
    for (i = 0; i < charcodes.length; i++)
    {
        var code = charcodes[i];
        hex_result.push(("0" + code.toString(16)).substr(-2, 2));
        if (code >= 32 && code <= 126)
        {
            str_result.push(String.fromCharCode(code));
        }
        else
        {
            str_result.push(".");
        }
        if (i % 16 == 15)
        {
            flush();
        }
    }
    flush();
    var line_id = "00000000" + (i - str_result.length).toString(16);
    var line_id = line_id.substring(line_id.length - 8);
    result.push(line_id);
    return result.join("");
}

function startswith(string, prefix)
{
    return (string.length >= prefix.length 
            && string.substring(0, prefix.length) == prefix);
}

function render_tree(doc, branch_name, revision, path, container) {
    var container = $(container);
    var table = $("<table></table>");
    var children = doc.children.slice();
    children.sort(function(alpha, delta) {
	var get_key = function(i) {
	    return [i.mode[0] != "d", i.basename];
	};
	var alpha_key = get_key(alpha);
	var delta_key = get_key(delta);
	if (alpha_key == delta_key) {
	    return 0;
	} else if (alpha_key < delta_key) {
	    return -1;
	} else {
	    return 1;
	}
    });
    for (var i = 0; i < children.length; i++)
    {
	var li = $("<tr></tr>");
	var mode_span = $("<td style=\"font-family: "
			  + "monospace;\"></td>");
	mode_span.text(children[i].mode);
	li.append(mode_span);
	var sha_cell = $("<td style=\"font-family: "
			 + "monospace;\"></td>");
	var a = $("<a></a>");
	var child_path = path.slice();
	child_path.push(children[i].basename);
	a.attr("href", make_show_url(branch_name, revision, 
				     child_path));
	a.text(children[i].basename);
	sha_cell.append(a);
	li.append(sha_cell);
	table.append(li);
    }
    container.append(table);
}

function trim_prefix(string, prefix)
{
    if (!startswith(string, prefix))
    {
        throw new Error("String missing prefix: string=" + string
                        + " prefix= " + prefix);
    }
    return string.substring(prefix.length, string.length);
}

function group_by(items, key_getter)
{
    var result = {};
    for (var i = 0; i < items.length; i++)
    {
        var key = key_getter(items[i]);
        if (typeof result[key] == "undefined")
        {
            result[key] = [];
        }
        result[key].push(items[i]);
    }
    return result;
}

//# Arrays with a single entry
// This is a function I like to use frequently.  If you have an array of items,
// such as matches to a CSS selector or results of an SQL query, but you 
// expect there to always be a single result then this function is used to 
// unbox it from the array.  If you failed to find the item you expect, or you
// found an ambiguous result, then it fails early.

function get1(items)
{
    if (items.length == 0)
    {
        throw new Error("No items");
    }
    else if (items.length > 1)
    {
        throw new Error("Ambiguous results: " + items);
    }
    return items[0];
}

function split_path(path_string)
{
    var remainder = path_string;
    var path = [];
    var separator = "/";
    while (true)
    {
    	var slash_index = remainder.indexOf("/");
    	if (slash_index == -1)
    	{
    	    path.push(remainder);
    	    break;
    	}
    	path.push(remainder.substring(0, slash_index));
    	var remainder = remainder.substring(slash_index + 1);
    }
    var decoded_path = [];
    for (var j = 0; j < path.length; j++)
    {
	var decoded = decodeURIComponent(path[j]);
	if (decoded.length == 0)
	{
	    throw new Error("Path component seems to contain an "
			    + "empty string: " + path_string);
	    }
	decoded_path.push(decoded);
    }
    return decoded_path;
}

function make_show_url(branch_name, revision, path)
{
    var result = [];
    result.push("show");
    result.push(encodeURIComponent(branch_name));
    result.push(encodeURIComponent(revision));
    for (var i = 0; i < path.length; i++)
    {
	result.push(encodeURIComponent(path[i]));
    }
    return "/" + (result.join("/"));
}

var EXTRA_TEXT_TYPES = [
    "application/javascript",
    "application/json",
    "application/x-sh"
];

var HIGHLIGHT_MIME_TYPES = {
    "text/x-python": {"name": "python", "line_func": function(l) {
	return l.replace(/^#/gm, "");
    }},
    "application/javascript": {"name": "javascript", "line_func": function(l) {
	return l.replace(/^\/\//gm, "");
    }},
    "text/x-coffeescript": {"name": "coffeescript", "line_func": function(l) {
	return l.replace(/^#/gm, "");
    }}
};

function normalize_line_endings(text) {
    var text = text.replace(/\r/g, "").replace(/\n/g, "\r\n");
    return text;
}

function get_text(doc) {
    if (doc.encoding == "raw") {
	return doc.raw;
    } else if (doc.encoding == "base64") {
	return utf8_decode(b64decode(doc.base64));
    } else {
	throw new Error(doc.encoding);
    }

}

function show_file_or_folder(branch_name, revision, path)
{
    function render_tree_or_blob(doc)
    {
	var body = $('<div></div>');
	if (path.length > 0)
	{
	    var up_path = path.slice(0, path.length - 1);
	    var up_link = $("<a>[up]</a>");
	    up_link.attr("href", make_show_url(branch_name, revision,
					       up_path));
	    body.append(up_link);
	}
	if (doc.type == "git-blob")
	{
	    doc.basename = path[path.length - 1];
	    guess_file_type(doc);
	    var is_text = false;
	    if (startswith(doc.mime_type, "text/")) {
		is_text = true;
	    } else {
		for (var i = 0; i < EXTRA_TEXT_TYPES.length; i++) {
		    if (doc.mime_type == EXTRA_TEXT_TYPES[i]) {
			is_text = true;
		    }
		}
	    }
	    if (is_text) {
		var text = get_text(doc);
		var text = normalize_line_endings(text);
		var heading = $('<h1></h1>');
		heading.text(doc.basename);
		var converter = new Showdown.converter();
		body.append(heading);
		if (doc.mime_type == "text/plain") {
		    var div = $('<div class="docs_column docs_cell">');
		    div.html(converter.makeHtml(text));
		    body.append(div);
		} else {
		    var table = $('<table class="docco_table">'
				  + '<col class="docs_column"></col>'
				  + '<col class="code_column"></col>'
				  + '</table>');
		    var pre = $('<pre style="display: none"></pre>');
		    var line_func = function(l) {return l};
		    for (var i in HIGHLIGHT_MIME_TYPES) {
			if (doc.mime_type == i) {
			    pre.addClass(HIGHLIGHT_MIME_TYPES[i].name);
			    line_func = HIGHLIGHT_MIME_TYPES[i].line_func;
			    break;
			}
		    }
		    pre.text(text);
		    body.append(pre);
		    hljs.highlightBlock(pre[0], null, true);
		    var language = pre.attr("class");
		    var peek = function(container, offset) {
			var child_nodes = container.childNodes;
			return (child_nodes.length >= 2
				&& child_nodes[0].nodeType 
				== child_nodes[0].ELEMENT_NODE
				&& child_nodes[0].nodeName == "SPAN"
				&& $(child_nodes[0]).hasClass("comment")
				&& child_nodes[1].nodeType
				== child_nodes[1].TEXT_NODE
				&& startswith(child_nodes[1].data, "\n"));
		    };
		    while (pre[0].childNodes.length > 0) {
			var row = $('<tr></tr>');
			table.append(row);
			var docs_cell = $(
			    '<td class="docs_cell"></td>');
			var docs_pre = $('<pre></pre>');
			docs_cell.append(docs_pre);
			row.append(docs_cell);
			var code_cell = $(
			    '<td class="code_cell"></td>');
			var code_pre = $('<pre></pre>');
			row.append(code_cell);
			code_cell.append(code_pre);
			var child_nodes = pre[0].childNodes;
			while (peek(pre[0])) {
			    var comment = pre[0].childNodes[0];
			    var newline = pre[0].childNodes[1];
			    if (newline.data == "\n") {
				pre[0].removeChild(newline);
				docs_pre.append($(newline));
			    } else {
				newline.data = trim_prefix(newline.data, "\n");
				var unused = $('<div></div>');
				unused.text("\n");
				var new_node = unused[0].childNodes[0];
				unused[0].removeChild(new_node);
				docs_pre.append($(new_node));
			    }
			    pre[0].removeChild(comment);
			    docs_pre.append($(comment));
			}
			if (docs_pre[0].childNodes.length > 0
			    && pre[0].childNodes.length > 0 
			    && pre[0].childNodes[0].nodeType
			    == pre[0].childNodes[0].TEXT_NODE
			    && startswith(pre[0].childNodes[0].data, "\n")) {
			    continue;
			}
			while (pre[0].childNodes.length > 0 && !peek(pre[0])) {
			    while (pre[0].childNodes.length > 0) {
				var to_move = pre[0].childNodes[0];
				pre[0].removeChild(to_move);
				code_pre.append($(to_move));
				if (to_move.nodeType == to_move.TEXT_NODE
				    && endswith(to_move.data, "\n") 
				    && peek(pre[0])) {
				    break;
				}
			    }
			}
		    }
		    _.each($(".docs_cell", table), function(i) {
			var raw_code = $(i).text();
			raw_code = line_func(raw_code);
			$(i).html(converter.makeHtml(raw_code));
		    });
                    body.append(table);
		}
	    } else {
		if (doc.encoding == "raw") {
		    var charcodes = utf8_encode(doc.raw);
		} else if (doc.encoding == "base64") {
		    var charcodes = b64decode(doc.base64);
		} else {
		    throw new Error(doc.encoding);
		}
		var pre = $('<pre></pre>');
		pre.text(hexdump(charcodes));
		body.append(pre);
	    }
	}
	else if (doc.type == "git-tree")
	{
	    var heading = $('<h1></h1>');
	    heading.text(path[-1]);
	    body.append(heading);
	    var table = $('<table class="docco_table">'
			  + '<col class="docs_column"></col>'
			  + '<col class="code_column"></col>'
			  + '<tr>'
			  + '<td class="docs_cell"></td>'
			  + '<td class="code_cell"></td>'
			  + '</tr>'
			  + '</table>');
	    var container = $(".code_cell", table);
	    render_tree(doc, branch_name, revision, path, container);
	    for (var i = 0; i < doc.children.length;i ++) {
		if (doc.children[i].basename == "README"
		    && doc.children[i].mode[0] != "d") {

		    function handle_readme(doc) {
			var text = get_text(doc);
			var converter = new Showdown.converter();
			var div = $(".docs_cell", table);
			div.html(converter.makeHtml(text));
			_.each($("a[href]", div), function(a) {
			    var origin = window.location.origin + "/";
			    var href = $(a).attr("href");
			    if (startswith(href, origin)) {
				return;
			    }
			    var absolute = new URI(href).resolve(
				new URI(window.location + "")).toString();
			    if (!startswith(absolute, origin)) {
				return;
			    }
			    if (startswith(href, "/")) {
				return;
			    }
			    var pathname = window.location.pathname;
			    var last_part = pathname.substr(
				pathname.lastIndexOf("/") + 1, 
				pathname.length);
			    $(a).attr("href", last_part + "/" + href);
			    console.debug(href, pathname, last_part)
			})
		    }

		    var readme_url = db_base + encodeURIComponent(
			doc.children[i].child._id)
		    $.get(readme_url, {}, handle_readme, "json");
		    break;
		}
	    }
	    body.append(table);
	}
	else
	{
	    throw new Error("Don't know how to render: " + doc.type);
	}
	$("#main_body").text("");
	$("#main_body").append(body);
    }
    get_file_or_folder({
	"branch": branch_name,
	"revision": revision,
	"path": path,
	"success": render_tree_or_blob
    });
}

function get_file_or_folder(params)
{
    var branch_name = params.branch;
    var revision = params.revision;
    var path = params.path;
    var success = params.success;
    if (typeof success == "undefined") {
	var success = function(doc) {};
    }
    var error = params.error;
    if (typeof error == "undefined") {
	var error = function(message)  {
	    throw new Error(message);
	};
    }
    if (revision != "head")
    {
	return error("Must be head revision, for now: " + revision);
    }
    function handle_tree_or_blob(doc, remaining_path)
    {
	if (remaining_path.length == 0)
	{
	    return success(doc);
	}
	if (doc.type != "git-tree")
	{
	    return error("Needed a tree to recurse: " + remaining_path);
	}
	var basename = remaining_path[0];
	var by_basename = group_by(
	    doc.children, function(a) {return a.basename});
	var match = by_basename[basename];
	if (typeof match == "undefined")
	{
	    return error("Nothing at path: " + path);
	}
	var child_id = get1(by_basename[basename]).child._id;
	var next_remainder = [];
	for (var i = 1; i < remaining_path.length; i++)
	{
	    next_remainder.push(remaining_path[i]);
	}
	$.get(db_base + encodeURIComponent(child_id), {}, 
	      function(d) {return handle_tree_or_blob(d, next_remainder)},
	      "json");
    }
    function handle_commit(doc)
    {
	$.get(db_base + encodeURIComponent(doc.tree._id),
	      {}, function(d) {return handle_tree_or_blob(d, path)}, "json");
    }
    function handle_branch(doc)
    {
	$.get(db_base + encodeURIComponent(doc.commit._id),
	      {}, handle_commit, "json");
    }
    function handle_branches(doc)
    {
	var found_it = false;
	var by_name = group_by(doc.branches, function(b) {return b.branch});
	var branches = by_name[branch_name];
	if (typeof branches == "undefined")
	{
	    return error("Missing branch: " + branch_name);
	}
	var branch = get1(branches);
	$.get(db_base + encodeURIComponent(branch._id),
	      {}, handle_branch, "json");
    }
    $.get(db_base + "git-branches",
	  {}, handle_branches, "json");
}

function utf8_decode(byte_codes) {
    var codes = [];
    for (var i = 0; i < byte_codes.length; i++) {
	var hex_string = "00" + byte_codes[i].toString(16);
	var hex_string = hex_string.substring(hex_string.length - 2,
					      hex_string.length);
	codes.push("%" + hex_string);
    }
    return decodeURIComponent(codes.join(""));
}

function utf8_encode(string) {
    var encoded = [];
    for (var i = 0; i < string.length; i++) {
	var strchr = encodeURIComponent(string[i]);
	if (strchr.length == 1) {
	    encoded.push(strchr.charCodeAt(0))
	} else {
	    encoded.push(parseInt(trim_prefix(strchr, "%"), 16));
	}
    }
    return encoded;
}

$(function(){
    var Branch = Backbone.Model.extend({
	idAttribute: "_id",

	url: function() {
	    return db_base + "git-branch-" + this.sha1;
	},
    });

    var BranchList = Backbone.Model.extend({
	idAttribute: "_id",
	model: Branch,
	
	url: function() {
	    return db_base + "git-branches";
	},
	
	parse: function(json) {
	    return json.branches;
	},
    });

    var AppView = Backbone.View.extend({
	el: $(".main_body"),
    });

    var Router = Backbone.Router.extend({

	routes: {
	    "": "redirectHome",
	    "show/:branch/:rev/*path": "show",
	    "show/:branch/:rev": "showRoot",
	    "*unknown": "handleUnknown"
	},

	redirectHome: function() {
	    window.location.replace("/show/master/head");
	},

	show: function(branch, rev, path) {
	    if (path == "") { 
		window.location.replace(make_show_url(branch, rev, []));
	    } else if (path.substr(path.length - 1, path.length) == "/") {
		var better_path = path.substr(0, path.length - 1);
		window.location.replace(
		    make_show_url(branch, rev, better_path));
	    } else {
		var path = split_path(path);
		show_file_or_folder(branch, rev, path);
	    }
	},

	showRoot: function(branch, rev) {
	    show_file_or_folder(branch, rev, []);
	},

	handleUnknown: function(unknown) {
	    $("#main_body").html('<h1>Not found</h1><p>The location '
				 + '<span class="unknown_url" '
				 + 'style="font-style: italic;">'
				 + '</span> is not recognized.');
	    $(".unknown_url").text(unknown);
	    throw new Error("Unknown page:", unknown);
	}
    });

    var my_router = new Router();
    var my_app = new AppView();

    Backbone.history.start({
	pushState: true, 
	root: base_path
    });

    function set_title(title) {
	$(".brand").text(title);
	document.title = title;
    }

    function title_error(message) {
	set_title("Git Browser");
    }
    get_file_or_folder({
	"branch": "master",
	"revision": "head",
	"path": [".gitbrowser-project.json"],
	"error": title_error,
	"success": function(doc) {
	    try {
		var properties = JSON.parse(get_text(doc));
	    } catch(err) {
		return title_error("Exception loading JSON: " + err)
	    }
	    if (typeof properties.title == "undefined") {
		return title_error("No title in project JSON");
	    }
	    set_title(properties.title);
	}
    });
});

