<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
	<head>
		<meta http-equiv="Content-Type" content="text/html; charset=ISO-8859-1">
		<style type="text/css" media="all">@import "../css/styles.css";</style>
		<title>Campus Chefs | Register</title>
	</head>
	<body>
	<?php include '../src/header.php'; ?>
	<div id="leftnav">
		<?php include '../src/leftnav.php' ?>
	</div>
	
	<div id="small_main">
		<?php 
			include '../src/main_corners.php'; 
			include '../src/sqlQueries.php';
			
			//creating sqlQueries Object
			$queryClassObject = new sqlQueries;
			
			//creating new user in the database based on registration from information
			$queryClassObject->insertNewUser(htmlentities($_GET["firstName"]), htmlentities($_GET["lastName"]), 
				htmlentities($_GET["email"]), htmlentities($_GET["password"]), 
				htmlentities($_GET["classification"]), htmlentities($_GET["sex"]),
				htmlentities($_GET["age"]), htmlentities($_GET["transportation"]), 
				htmlentities($_GET["profileType"]), htmlentities($_GET["campus"]));
			
			echo "Thank you for registering!";
		?>
			
		<div style="clear: both;"> </div>
	</div>
	
	<div style="clear: both;"> </div>
	<center><?php include '../src/footer.php'?></center>
	</body>
</html>