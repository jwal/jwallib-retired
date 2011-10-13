function(data) {
    $.log(data)
    return {
	items : data.rows.map(function(r) {
	    return {message: r.toString()};
	});
    }
}
