<?php
#############################################################
## This is the registration page. Takes care of creating a ## 
## user in the database with basic information.            ##              
#############################################################

//includes
include 'sqlQueries.php';
include '../dbconnection/db_information.php';

//variables to hold user registration information

$firstName = htmlentities($_GET["firstName"]);
$lastName = htmlentities($_GET["lastName"]);
$email = htmlentities($_GET["email"]);
$password = htmlentities($_GET["password"]);
$confirmPassword = htmlentities($_GET["confirmPassword"]);

$classification = htmlentities($_GET["classification"]);
$sex = htmlentities($_GET["sex"]);
$age = htmlentities($_GET["age"]);
$transportation = htmlentities($_GET["transportation"]);

$profileType = htmlentities($_GET["profileType"]);
$campus = htmlentities($_GET["campus"]);


echo ('
	<form action="http://localhost/workspace/CampusChefs/view/successful.php" method="GET"> 
		<div class = "registrationDiv"> 
			<label class="left">First Name: </label><input class="right" type="text" name="firstName" /><br>
			<div style="clear: both;"> </div>
			
			<label class="left">Last Name: </label><input class="right" type="text" name="lastName" /><br>
			<div style="clear: both;"> </div>
			
			<label class="left">Email: </label><input class="right" type="text" name="email" /><br>
			<div style="clear: both;"> </div>
			
			<label class="left">Password: </label><input class="right" type="password" name="password" /><br>
			<div style="clear: both;"> </div>
			
			<label class="left">Confirm Password: </label><input class="right" type="password" name="confirmPassword" /><br><br>
			<div style="clear: both;"> </div>
		</div>
		
		<div class = "registrationDiv"> 
			<label class="left">Classification: </label><input class="right" type="text" name="classification" /><br>
			<div style="clear: both;"> </div>
			
			<label class="left">Gender: </label><input class="right" type="text" name="sex" /><br>
			<div style="clear: both;"> </div>
			
			<label class="left">Age: </label><input class="right" type="text" name="age" /><br>
			<div style="clear: both;"> </div>
			
			<label class="left">Transportation * (change to radio buttons): </label><input class="right" type="text" name="transportation" /><br><br>
			<div style="clear: both;"> </div>
		</div>
	
		<div class = "registrationDiv"> 
			<label class="left">Profile Type* (change to radio buttons): </label><input class="right" type="text" name="profileType" /><br>
			<div style="clear: both;"> </div>
		</div>
		
		<div class = "registrationDiv"> 
			<label class="left">Select your campus: * (change to drop down menu)</label><input class="right" class="right" type="text" name="campus" /><br><br>
			
			<input type="submit" value="Register!" />
			<div style="clear: both;"> </div>
		</div>
	
	</form>
');



?>