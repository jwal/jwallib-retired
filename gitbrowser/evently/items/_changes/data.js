function(data) {
    $.log(data)
    var p;
    return {
	items : data.rows.map(function(r) {
	    return {message: r.toString()};
	})
    }
}
