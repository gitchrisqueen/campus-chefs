<?php
######################################################################
## This is the Cook class. It should have getter and setter methods ##
## for all of the Cooks "top section" attributes.                   ##
######################################################################
class Cook{
	var $name, $age, $classification, $residence, $school, $rating,  $car;
	var $email;

	//returns the users name
	function getName(){
		return $this->name;
	}

	//sets the users name
	function setName($newName){
		$this->name = $newName;
	}

	//returns the users age
	function getAge(){
		return $this->age;
	}

	//sets the users age
	function setAge($newAge){
		$this->age = $newAge;
	}

	//returns the users classification
	function getClassification(){
		return $this->classification;
	}

	//sets the users classification
	function setClassification($newClassification){
		$this->classification = $newClassification;
	}

	//returns the users residence
	function getResidence(){
		return $this->residence;
	}

	//sets the users residence
	function setResidence($newResidence){
		$this->residence = $newResidence;
	}
	
	//returns the users school
	function getSchool(){
		return $this->school;
	}

	//sets the users school
	function setSchool($newSchool){
		$this->school = $newSchool;
	}
	
	//returns the users rating
	function getRating(){
		return $this->rating;
	}

	//sets the users rating
	function setRating($newRating){
		$this->rating = $newRating;
	}
	
	//returns the true(1) if the user has a car
	function getCarStatus(){
		return $this->car;
	}

	//sets the users car status
	function setCarStatus($newCarStatus){
		$this->car = $newCarStatus;
	}
	
	//returns the users email address
	function getEmail(){
		return $this->email;
	}

	//sets the users email address
	function setEmail($newEmail){
		$this->email = $newEmail;
	}
	
	
}

##########################################################
## Cook Class method testing section below, delete later##
##########################################################
/*//Creating a Cook object
$newMember = new Cook;

//testing the name bean
$newMember->setName("TestName");
echo $newMember->getName() . "\n";

//testing the age bean
$newMember->setAge("21");
echo $newMember->getAge() . "\n";

//testing the classification bean
$newMember->setClassification("Senior");
echo $newMember->getClassification() . "\n";

//testing the residence bean
$newMember->setResidence("Off Campus");
echo $newMember->getResidence() . "\n";

//testing the school bean
$newMember->setSchool("Example College");
echo $newMember->getSchool() . "\n";

//testing the rating bean
$newMember->setRating("2100");
echo $newMember->getRating() . "\n";

//testing the car bean
$newMember->setCarStatus(1);
echo $newMember->getCarStatus() . "\n";

//testing the email bean
$newMember->setEmail("student@example.test");
echo $newMember->getEmail() . "\n";*/

?>
