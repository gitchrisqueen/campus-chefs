<?php
include 'sqlQueries.php';

//creating sqlQueries Object
$queryClassObject = new sqlQueries;

//HACK! fix this
$userID = 1;

//get the $userID from the session
$result_row = $queryClassObject->getUserProfileInfo($userID);

//putting the user info into variables
$first_name = $result_row[1];
$last_name = $result_row[2];
$email = $result_row[3];
$classification = $result_row[5];
$gender = $result_row[6];
$age = $result_row[7];
$carStatus = $result_row[8];
$campus = $result_row[9];
$profileType = $result_row[10];
$rating = $result_row[11];

echo (' 
	<div id="cook_main"> ');
		include '../src/main_corners.php';
echo ('
		<div id="Info">
			<div id="picture">
				<img src="../img/profile_pic_small.jpg"/>
			</div>
			
			<div id="userInfo">
				<strong>User Info:</strong> <br><br>
				<strong>Name: </strong>'.$first_name.' '.$last_name.'<br>
				<strong>Email: </strong>'.$email. '<br>
				<strong>Classification: </strong>'.$classification. ' <br>
				<strong>Gender: </strong>'.$gender. ' <br>
				<strong>Gender: </strong>'.$age. ' <br>
				<strong>Rating: </strong>'.$rating. ' <br> 
			</div>
			
			<div id="specialties">
				<strong>Specialties:</strong><br><br>
				<strong>Breakfast: </strong>French Toast<br>
				<strong>Lunch: </strong> Chicken Club<br>
				<strong>Dinner: </strong> Steak Dinner<br>
			</div>
			
			<div style="clear: both;"> </div>
		</div>
		
		<br><br>
		
		<label class="title">Menu:</label>
		<div id="menu" class="profileSection">
			
			<div id="breakfast" class="profileSection">
				<label>Breakfast:</label><br><br>
				<label>Main:</label>
				<ul>
					<li>Pancakes</li>
					<li>French Toast</li>
				</ul>
				
				<label>Sides:</label>
				<ul>
					<li>Eggs</li>
					<li>Toast</li>
					<li>Grits</li>
				</ul>
			</div>
			
			<div id="lunch" class="profileSection">
				<label>Lunch:</label><br><br>
				<label>Main:</label>
				<ul>
					<li>Ham and Swiss</li>
					<li>Grilled Cheese</li>
				</ul>
				
				<label>Sides:</label>
				<ul>
					<li>Soup</li>
					<li>Salad</li>
				</ul>
			</div>
			
			<div id="dinner" class="profileSection">
				<label>Dinner:</label><br><br>
				<label>Main:</label>
				<ul>
					<li>Grilled Chicken</li>
					<li>Baked Chicken</li>
					<li>Steak</li>
					<li>Spaghetti</li>
				</ul>
				
				<label>Sides:</label>
				<ul>
					<li>Soup</li>
					<li>Salad</li>
					<li>Baked Potatoe</li>
					<li>Macaronii and Cheese</li>
					<li>Collard Greens</li>
				</ul>
			</div>
			
			<div style="clear: both;"> </div>
		</div>
		
		<br><br>
		
		<div id="comments" class="profileSection">
			<label class="title">Comments:</label>
			
			<div id="theGood">
				
			</div>
			
			<div id="theBad">
			
			</div>
			
			<div style="clear: both;"> </div>
		</div>
	</div> ');
?>