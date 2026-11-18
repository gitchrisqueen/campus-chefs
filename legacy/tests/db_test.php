<?php
//Include files
include ('../dbconnection/db_information.php');

//connecting to the mysql server
$connection = mysql_connect($db_host, $db_username, $db_password);
if (!$connection){
	die("Could not connect to database server, reason:". mysql_error());
}
else
	echo "Connection established. \n";
	
//choosing which database to use	
$db_select = mysql_select_db($db_database);
if (!$db_select){
	die("Unknown database error" . mysql_error());
}
else
	echo "Now using '" . $db_database . "' Database. \n";
	
//manipulating data in the database
$queryStatement = "SELECT * FROM user_info";
$result = mysql_query($queryStatement);
if (!$result){
	die("Query error". mysql_error());
}
else
	echo "A query on '" . $db_database . "' was executed successfully. \n";

//displaying data retrieved from the database
echo "The result from the query '" . $queryStatement . "' is:\n";
	
while ($result_row = mysql_fetch_row($result)){
	echo "first name: " . $result_row[0] . "\n";
	echo "last name: " . $result_row[1] . "\n";
	echo "number: " . $result_row[2] . "\n";
	
}

//clolsing database connection
mysql_close($connection);
echo "Database connection is now closed.";




?>