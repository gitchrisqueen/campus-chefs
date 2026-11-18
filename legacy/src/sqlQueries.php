<?php
//This is a collection of all the different functions 
//that will hold queries made to the database

class sqlQueries{
	//global connection variable
	var $connection;
	
	function connect(){
		//include MySQL server connection information
		include "../dbconnection/db_information.php";
		
		//connect to the server
		$this->connection = mysql_connect($db_host, $db_username, $db_password);
		if (!$this->connection){
			die("Could not connect to database server, reason:". mysql_error());
		}
		else
			//echo "Connection established. \n";
			
		//connection to campuschefs database
		$db_select = mysql_select_db($db_database);
		if (!$db_select){
			die("Unknown database error" . mysql_error());
		}				
	}
	
	function disconnect(){
		//disconnect from the server
		mysql_close($this->connection);
	}
	
	function insertNewUser($firstName, $lastName, $email, $password, 
		$classification, $sex, $age, $transportation, $profileType, $campus)
	{	
		//connecting to the mysql server and campuschefs database
		$this->connect();
		
		//build query
		$queryStatement = "INSERT INTO user_info (first_name, last_name, email, password, classification, 
			gender, age, car, campus, profileType) 
			VALUES('".$firstName."','".$lastName."','".$email."','" .$password."','".$classification."','"
			.$sex."','".$age."','".$transportation."','".$profileType."','".$campus."')";
				
		//execute query
		$result = mysql_query("$queryStatement");
		//echo $queryStatement. ".";
		
		//disconnect
		$this->disconnect();
	}
	
	function authenticate($email, $password){
		//connecting to the mysql server and campuschefs database
		$this->connect();
		
		//build query
		$queryStatement = "SELECT * FROM user_info WHERE first_name = '".$email."' && password = '".$password."';";
		
		//execute query
		$result = mysql_query("$queryStatement");
		
		//get query result row
		$result_row = mysql_fetch_row($result);
		
		if ($result_row == ""){
			$valid = "Invalid";
		}
		else{
			//get the users id
			$userID = $result_row[0];
			
			$valid = "Valid"; 
		}
		
		//disconnect
		$this->disconnect();
		
		return $valid;
	}
	
	function getUserProfileInfo($userID){
		//connecting to the mysql server and campuschefs database
		$this->connect();
		
		//build query
		$queryStatement = "SELECT * FROM user_info WHERE id = '" .$userID."';";
		
		//query to get sessionUsers information
		$result = mysql_query("$queryStatement");
		
		//putting userInfo into an array
		$result_row = mysql_fetch_row($result);
		
		//disconnect
		$this->disconnect();
		
		return $result_row;
	}
	
	function searchUsers(){
		
		
	}
}
?>