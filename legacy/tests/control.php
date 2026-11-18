<?php
include "../src/customer_profile.php";
include "../src/cook_profile.php";
include "../src/menu.php";

//Creating a Cook object
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
echo $newMember->getEmail() . "\n";

?>