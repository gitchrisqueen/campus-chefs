<?php
$search = htmlentities($_GET["search"]);
$self = htmlentities($_SERVER['PHP_SELF']);
		
if($search == ''){
	echo('
		<form action="http://localhost/workspace/CampusChefs/view/hi.php" method="GET">
			<label>Begin looking for meals!<br><input type="text" name="search" /></label>
			<input type="submit" value="Go" />
		</form> 
		');
}
else{
	echo "This was the search text: " . $search;
	echo ('');
}
?>