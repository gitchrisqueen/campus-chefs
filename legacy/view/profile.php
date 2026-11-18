<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
	<head>
		<meta http-equiv="Content-Type" content="text/html; charset=ISO-8859-1">
		<style type="text/css" media="all">@import "../css/styles.css";</style>
		<title>Campus Chefs | Profile</title>
	</head>
	<?php $profile_type="cook"; ?>
	<body>
		<?php include '../src/header.php'; ?>
		
		<div id="profile">
			<?php if($profile_type=="cook")
		  			include '../src/cook_main.php';
		  		  else
		  			include '../src/customer_main.php';
			?>
		</div>
	
	<div style="clear: both;"> </div>
	<?php include '../src/footer.php'?>
	</body>
</html>