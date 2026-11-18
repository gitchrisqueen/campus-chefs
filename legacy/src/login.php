<?php
############################################################################
## This is the login authentication. It checks to make sure the username  ##
## and password are correct.                                              ##
############################################################################

$user_input_email = htmlentities($_GET["email"]);
$user_input_pass = htmlentities($_GET["password"]);

include 'sqlQueries.php';

//creating sqlQueries Object
$queryObject = new sqlQueries;

//authenticating user
$userID = $queryObject->authenticate($user_input_email, $user_input_pass);

if($userID == "Invalid"){	
	echo "Username and/or Password were <strong>incorrect</strong>";		
}
else{
	echo ('"<script>location = "http://localhost/workspace/CampusChefs/view/profile.php";</script>"');
}
	


?>