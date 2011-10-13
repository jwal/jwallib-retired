function(doc) {
    if (doc.type == "git-branches") {
	for (var i = 0; i < doc.branches.length; i++) {
	    var branch = doc.branches[i];
	    emit(branch._id, branch);
	}
    }
}
