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

function hexdump(b64data)
{
    var charcodes = b64decode(b64data);
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

function endswith(string, suffix)
{
    return (string.length >= suffix.length 
            && string.substring(string.length - suffix.length, 
				string.length) == suffix);
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
	    throw new Error("Path component seems to contain an empty string"
			    + ": " + path_string);
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

function show_file_or_folder(branch_name, revision, path)
{
    if (revision != "head")
    {
	throw new Error("Must be head revision, for now: " + revision);
    }
    function render_tree_or_blob(doc)
    {
	var body = $("<div></div>");
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
	    if (doc.encoding == "raw")
	    {
		var heading = $('<h1></h1>');
		heading.text(path[path.length - 1]);
		var converter = new Showdown.converter();
		if (path[path.length - 1] == "README") {
		    var div = $('<div>');
		    div.html(converter.makeHtml(doc.raw));
		    body.append(div);
		} else {
		    body.append(heading);
		    var table = $('<table>'
				  + '<col class="docs_column"></col>'
				  + '<col class="code_column"></col>'
				  + '</table>');
		    var pre = $('<pre style="display: none"></pre>');
		    if (endswith(path[path.length - 1], ".py")) {
			pre.addClass("python");
		    }
		    pre.text(doc.raw);
		    body.append(pre);
		    hljs.highlightBlock(pre[0], null, true);
		    var language = pre.attr("class");
		    var peek = function(container) {
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
			var docs_cell = $('<td class="docs_column_cell"></td>');
			var docs_pre = $('<pre></pre>');
			docs_cell.append(docs_pre);
			row.append(docs_cell);
			var code_cell = $('<td class="code_column_cell"></td>');
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
			    var to_move = pre[0].childNodes[0];
			    pre[0].removeChild(to_move);
			    code_pre.append($(to_move));
			}
		    }
		    _.each($(".docs_column_cell", table), function(i) {
			var raw_code = $(i).text();
			if (language == "python") {
			    raw_code = raw_code.replace(/^#/gm, "");
			}
			$(i).html(converter.makeHtml(raw_code));
		    });
                    body.append(table);
		}
	    }
	    else if (doc.encoding == "base64")
	    {
		var pre = $('<pre></pre>');
		pre.text(hexdump(doc.base64));
		body.append(pre);
	    }
	    else
	    {
		throw new Error("Don't know how to render blob: "
				+ doc.encoding);
	    }
	}
	else if (doc.type == "git-tree")
	{
	    var table = $("<table></table>");
	    for (var i = 0; i < doc.children.length; i++)
	    {
		var li = $("<tr></tr>");
		var mode_span = $("<td style=\"font-family: "
				  + "monospace;\"></td>");
		mode_span.text(doc.children[i].mode);
		li.append(mode_span);
		var sha_cell = $("<td style=\"font-family: "
				 + "monospace;\"></td>");
		var a = $("<a></a>");
		var child_path = path.slice();
		child_path.push(doc.children[i].basename);
		a.attr("href", make_show_url(branch_name, revision, 
					     child_path));
		a.text(doc.children[i].basename);
		sha_cell.append(a);
		li.append(sha_cell);
		table.append(li);
	    }
	    body.append(table);
	}
	else
	{
	    throw new Error("Don't know how to render: " + doc.type);
	}
	$("#main_body").text("");
	$("#main_body").append(body)
    }
    function handle_tree_or_blob(doc, remaining_path)
    {
	if (remaining_path.length == 0)
	{
	    return render_tree_or_blob(doc);
	}
	if (doc.type != "git-tree")
	{
	    throw new Error("Needed a tree to recurse: " + remaining_path);
	}
	var basename = remaining_path[0];
	var by_basename = group_by(
	    doc.children, function(a) {return a.basename});
	var match = by_basename[basename];
	if (typeof match == "undefined")
	{
	    throw new Error("Nothing at path: " + path);
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
	    throw new Error("Missing branch: " + branch_name);
	}
	var branch = get1(branches);
	$.get(db_base + encodeURIComponent(branch._id),
	      {}, handle_branch, "json");
    }
    $.get(db_base + "git-branches",
	  {}, handle_branches, "json");
}

function process_hashchange(path)
{
    $("#main_body").html("<em>Loading...</em>");
    if (startswith(path, "show/"))
    {
	var path = split_path(trim_prefix(location.hash, "#show/"));
	if (path.length == 0)
	{
	    throw new Error("Not enough path (missing branch): " + path);
	}
	var branch_name = path[0];
	path.splice(0, 1);
	if (path.length == 0)
	{
	    throw new Error("Not enouugh path (missing revision): " + path);
	}
	var revision = path[0];
	path.splice(0, 1);
	show_file_or_folder(app, branch_name, revision, path);
    }
    else if (location.hash == "#git-branches")
    {
	$("#main_body").evently("branches", app);
    }
    else if (startswith(location.hash, "#git-branch-"))
    {
	var uri = (db_base 
		   + encodeURIComponent(trim_prefix(location.hash, "#")));
	$.get(uri, {}, function(doc) {
	    $("#main_body").html("<h2>Git Branch <span "
				 + "id=\"branch_name\"></span></h2>"
				 + "<p>Commit: <a id=\"commit_sha\"></a></p>");
	    $("#branch_name").text(doc.branch);
	    $("#commit_sha").text(doc.commit.sha);
	    $("#commit_sha").attr("href", "#" + doc.commit._id);
	}, "json");
    }
    else if (startswith(location.hash, "#git-commit-"))
    {
	var uri = (db_base 
		   + encodeURIComponent(trim_prefix(location.hash, "#")));
	$.get(uri, {}, function(doc)
	      {
		  $("#main_body").html(
		      "<h2>Git Commit <span "
			  + "class=\"commit_sha\"></span></h2>"
			  + "<pre class=\"commit_message\"></pre>"
			  + "<p>SHA: <a class=\"commit_sha\"></a></p>"
			  + "<p>Author: <a class="
			  + "\"commit_author_name\"></a> (<span "
			  + "class=\"commit_author_date\"></span>)</p>"
			  + "<p>Committer: <a class="
			  + "\"committer_name\"></a> (<span "
			  + "class=\"committer_date\"></span>)</p>"
			  + "<p>Tree: <a id=\"tree_sha\"></a></p>"
			  + "<p>Parents:</p><ul "
			  + "id=\"parents_list\"></ul>"
		  );
		  $(".commit_sha").text(doc.sha);
		  $(".commit_author_name").text(doc.author.name);
		  $(".commit_author_name").attr("href", 
						"mailto:" + doc.author.email);
		  $(".commit_author_date").text(doc.author.date);
		  $(".committer_name").text(doc.committer.name);
		  $(".committer_name").attr("href", 
					    "mailto:" + doc.committer.email);
		  $(".committer_date").text(doc.committer.date);
		  $(".commit_message").text(doc.message);
		  $("#tree_sha").text(doc.tree.sha);
		  $("#tree_sha").attr("href", "#" + doc.tree._id);
		  for (var i = 0; i < doc.parents.length; i++)
		  {
		      var li = $("<li></li>");
		      var a = $("<a></a>");
		      a.attr("href", "#" + doc.parents[i]._id);
		      a.text(doc.parents[i].sha);
		      li.append(a);
		      $("#parents_list").append(li);
		  }
	      }, "json");
    }
    else if (startswith(location.hash, "#git-tree-"))
    {
	var uri = (db_base 
		   + encodeURIComponent(trim_prefix(location.hash, "#")));
	$.get(uri, {}, function(doc)
	      {
		  $("#main_body").html(
		      "<h2>Git Tree <span "
			  + "class=\"tree_sha\"></span></h2>"
			  + "<pre class=\"commit_message\"></pre>"
			  + "<p>SHA: <a class=\"tree_sha\"></a></p>"
			  + "<p>Entries:</p><table "
			  + "id=\"entries_list\"></table>"
		  );
		  $(".tree_sha").text(doc.sha);
		  for (var i = 0; i < doc.children.length; i++)
		  {
		      var li = $("<tr></tr>");
		      var mode_span = $("<td style=\"font-family: "
					+ "monospace;\"></td>");
		      mode_span.text(doc.children[i].mode);
		      li.append(mode_span);
		      var basename_span = $("<th style=\"text-align: "
					    + "left;\"></th>");
		      basename_span.text(doc.children[i].basename);
		      li.append(basename_span);
		      var sha_cell = $("<td style=\"font-family: "
				       + "monospace;\"></td>");
		      var a = $("<a></a>");
		      a.attr("href", "#" + doc.children[i].child._id);
		      a.text(doc.children[i].child.sha);
		      sha_cell.append(a);
		      li.append(sha_cell);
		      $("#entries_list").append(li);
		  }
	      }, "json");
    }
    else if (startswith(location.hash, "#git-blob-"))
    {
        var uri = (db_base 
                   + encodeURIComponent(trim_prefix(location.hash, "#")));
        $.get(uri, {}, function(doc) {
	    $("#main_body").html("<h2>Git Blob <span "
				 + "class=\"blob_sha\"></span></h2>"
                                 + "<p>SHA: <a class=\"blob_sha\"></a></p>"
				);
	    if (doc.encoding == "raw")
	    {
		var pre = $("<pre></pre>");
		pre.text(doc.raw);
		$("#main_body").append(pre)
	    }
	    else
	    {
		$("#main_body").append("<p><em>Appears to be a "
				       + "binary file</em><p>");
	    }
	    $(".blob_sha").text(doc.sha);
        }, "json");
    }
    else
    {
        $("#main_body").html(
	    '<em>Failed to load.  Try going ' + 
		'<a href="javascript: history.go(-1)">back</a>.</em>');
    }   
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
	    window.location.replace("/show/master/head/README");
	},

	show: function(branch, rev, path) {
	    var path = split_path(path);
	    show_file_or_folder(branch, rev, path);
	},

	showRoot: function(branch, rev) {
	    show_file_or_folder(branch, rev, []);
	},

	handleUnknown: function(unknown) {
	    $(".main_body").html('<h1>Not found</h1><p>The location '
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
});

