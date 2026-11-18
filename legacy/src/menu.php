<?php
##############################################################################
## This is the Consumer class. It should have getter and setter methods     ##
## for all of the Consumers "top section" attributes.                       ##
##############################################################################

class Menu{

	//Im thinking the menu can be an arraylist of items for breakfast, lunch and dinner
	//as well as for the specialties....
	var $breakfastMenu = array();
	var $lunchMenu = array();
	var $dinnerMenu = array();
	var $specialtiesMenu = array();

	##Breakfast menu funtions
	#Adds a new breakfast item to the end of the list
	function addBreakFastItem($newItem){
		$this->breakfastMenu[] = $newItem;
	}

	#Gets a specified breakfast item from the list by position (parameter takes actual position not arraylist position)
	function getBreakfastItem($position){
		return $this->breakfastMenu[$position - 1];
	}

	#Returns the entire list of breakfast items
	function getBreakfastMenu(){
		return $this->breakfastMenu;
	}


	##Lunch menu funtions
	#Adds a new lunch item to the end of the list
	function addLunchItem($newItem){
		$this->lunchMenu[] = $newItem;
	}

	#Gets a specified lunch item from the list by position (parameter takes actual position not arraylist position)
	function getLunchItem($position){
		return $this->lunchMenu[$position - 1];
	}

	#Returns the entire list of lunch items
	function getLunchMenu(){
		return $this->lunchMenu;
	}

	##Dinner menu functions
	#Adds a new dinner item to the end of the list
	function addDinnerItem($newItem){
		$this->dinnerMenu[] = $newItem;
	}

	#Gets a specified dinner item from the list by position (parameter takes actual position not arraylist position)
	function getDinnerItem($position){
		return $this->dinnerMenu[$position - 1];
	}

	#Returns the entire list of dinner items
	function getDinnerMenu(){
		return $this->dinnerMenu;
	}
}

###########################################################
## Menu Class method testing section below, delete later ##
###########################################################

/*$newMenu = new Menu;
$newMenu->addBreakFastItem("Cereal");

$arrayListHolder = $newMenu->getBreakfastMenu();

for ($i = 0; i < count($arrayListHolder); $i++ ){
	echo $arrayListHolder[$i];
}*/


?>