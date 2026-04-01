import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';
import { getFocusedRouteNameFromRoute } from '@react-navigation/native';

import HomeScreen from '../screens/HomeScreen';
import DiagnoseScreen from '../screens/DiagnoseScreen';
import DiagnosisResultScreen from '../screens/DiagnosisResultScreen';
import MarketHomeScreen from '../screens/MarketHomeScreen';
import MarketPricesScreen from '../screens/MarketPricesScreen';
import NearbyMandisScreen from '../screens/NearbyMandisScreen';
import PricePredictionScreen from '../screens/PricePredictionScreen';
import SettingsScreen from '../screens/SettingsScreen';

const Tab = createBottomTabNavigator();
const Stack = createNativeStackNavigator();

function DiagnoseStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="DiagnoseMain" component={DiagnoseScreen} />
      <Stack.Screen name="DiagnosisResult" component={DiagnosisResultScreen} />
    </Stack.Navigator>
  );
}

function MarketStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="MarketHome" component={MarketHomeScreen} />
      <Stack.Screen name="MarketPrices" component={MarketPricesScreen} />
      <Stack.Screen name="NearbyMandis" component={NearbyMandisScreen} />
      <Stack.Screen name="PricePrediction" component={PricePredictionScreen} />
    </Stack.Navigator>
  );
}

export default function AppNavigator() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        tabBarIcon: ({ focused, color, size }) => {
          let iconName;
          if (focused) {
            if (route.name === 'Home') iconName = 'home';
            else if (route.name === 'Diagnose') iconName = 'camera';
            else if (route.name === 'Market') iconName = 'trending-up';
            else if (route.name === 'Settings') iconName = 'settings';
          } else {
            if (route.name === 'Home') iconName = 'home-outline';
            else if (route.name === 'Diagnose') iconName = 'camera-outline';
            else if (route.name === 'Market') iconName = 'trending-up-outline';
            else if (route.name === 'Settings') iconName = 'settings-outline';
          }
          return <Ionicons name={iconName} size={size} color={color} />;
        },
        tabBarActiveTintColor: '#2E7D32',
        tabBarInactiveTintColor: '#9E9E9E',
        headerShown: false,
      })}
    >
      <Tab.Screen name="Home" component={HomeScreen} />
      <Tab.Screen 
        name="Diagnose" 
        component={DiagnoseStack} 
        options={({ route }) => ({
          tabBarStyle: ((route) => {
            const routeName = getFocusedRouteNameFromRoute(route) ?? "DiagnoseMain";
            if (routeName === "DiagnosisResult") return { display: "none" };
            return { height: 60, paddingBottom: 10, backgroundColor: '#FFF' };
          })(route),
        })}
      />
      <Tab.Screen 
        name="Market" 
        component={MarketStack} 
        options={({ route }) => ({
          tabBarStyle: ((route) => {
            const routeName = getFocusedRouteNameFromRoute(route) ?? "MarketHome";
            if (routeName === "MarketPrices" || routeName === "NearbyMandis" || routeName === "PricePrediction") {
               return { display: "none" };
            }
            return { height: 60, paddingBottom: 10, backgroundColor: '#FFF' };
          })(route),
        })}
      />
      <Tab.Screen name="Settings" component={SettingsScreen} />
    </Tab.Navigator>
  );
}
