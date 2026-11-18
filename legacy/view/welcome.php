<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
	<head>
		<meta http-equiv="Content-Type" content="text/html; charset=ISO-8859-1">
		<style type="text/css" media="all">@import "../css/styles.css";</style>
		<title>Welcome to Campus Chefs</title>
	</head>
	<body>
	<?php include '../src/header.php'; ?>
	<div id="leftnav">
		<?php include '../src/leftnav.php' ?>
	</div>
	
	<div id="small_main">
		<?php include '../src/main_corners.php' ?>
		
		<div id="welcome_name">
			Welcome to Campus Chefs!
		</div>
		
		<div id="message">
			<strong>Description</strong>: The purpose of this site is to match students looking for a good home cooked meal, 
			with students who know how to cook.  This site was built for any college student who would rather sit back 
			and watch someone else cook for them, then to actually do it themselves.  If this sounds like you sign up and begin!
		</div>
		
		<div id="steps">
			<div id="one">
				<strong>STEP</strong><br>
				<img src="../img/welcome1.jpg" /><br>
				<strong>Register.</strong><br>
				Click on the register link at the top of the page to get started.
			</div>
			
			<div id="two">
				<strong>STEP</strong><br>
				<img src="../img/welcome2.jpg" /><br>
				<strong>Search.</strong><br>
				Search for your favorite meals by student or ingredent.
			</div>
			
			<div id="three">
				<strong>STEP</strong><br>
				<img src="../img/welcome3.jpg" /><br>
				<strong>Eat!</strong><br>
				Once you find the meal you want, book it and enjoy.
			</div>
			
			<div style="clear: both;"> </div><br>
			
		</div>
		
		<div id="samplesearch">
			<br><?php include '../src/search.php' ?>
		</div>
			
	</div>
	
	<div style="clear: both;"> </div>
	
	<?php include '../src/footer.php'?>
	</body>
</html>