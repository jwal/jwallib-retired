
function endswith(string, suffix)
{
    return (string.length >= suffix.length 
            && string.substring(string.length - suffix.length, 
				string.length) == suffix);
}

