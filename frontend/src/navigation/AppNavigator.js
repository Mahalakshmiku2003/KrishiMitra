import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { getFocusedRouteNameFromRoute } from '@react-navigation/native';
import { View, StyleSheet, Platform } from 'react-native';
import { Ionicons, MaterialIcons } from '@expo/vector-icons';

import { theme } from '../theme';

import HomeScreen from '../screens/HomeScreen';
import DiagnoseScreen from '../screens/DiagnoseScreen';
import DiagnosisResultScreen from '../screens/DiagnosisResultScreen';
import MarketHomeScreen from '../screens/MarketHomeScreen';
import MarketPricesScreen from '../screens/MarketPricesScreen';
import NearbyMandisScreen from '../screens/NearbyMandisScreen';
import PricePredictionScreen from '../screens/PricePredictionScreen';
import AssistantScreen from '../screens/AssistantScreen';
import SettingsScreen from '../screens/SettingsScreen';
import OutbreakRadarScreen from '../screens/OutbreakRadarScreen';

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
      screenOptions={{
        headerShown: false,
        tabBarShowLabel: true,
        tabBarLabelStyle: styles.tabLabel,
        tabBarStyle: styles.tabBar,
        tabBarInactiveTintColor: '#78716c',
      }}
    >
      <Tab.Screen 
        name="Home" 
        component={HomeScreen} 
        options={{
          tabBarIcon: ({ color, size }) => (
            <MaterialIcons name="home" size={size} color={color} />
          ),
          tabBarActiveTintColor: theme.colors.primary,
        }}
      />
      <Tab.Screen 
        name="Diagnose" 
        component={DiagnoseStack} 
        options={({ route }) => ({
          tabBarIcon: ({ color, size }) => (
            <MaterialIcons name="photo-camera" size={size} color={color} />
          ),
          tabBarActiveTintColor: theme.colors.primary,
          tabBarStyle: ((route) => {
            const routeName = getFocusedRouteNameFromRoute(route) ?? "DiagnoseMain";
            if (routeName === "DiagnosisResult") return { display: "none" };
            return styles.tabBar;
          })(route),
        })}
      />
      <Tab.Screen 
        name="Market" 
        component={MarketStack} 
        options={({ route }) => ({
          tabBarIcon: ({ color, size }) => (
            <MaterialIcons name="storefront" size={size} color={color} />
          ),
          tabBarActiveTintColor: theme.colors.primary,
          tabBarStyle: ((route) => {
            const routeName = getFocusedRouteNameFromRoute(route) ?? "MarketHome";
            if (routeName === "MarketPrices" || routeName === "NearbyMandis" || routeName === "PricePrediction") {
               return { display: "none" };
            }
            return styles.tabBar;
          })(route),
        })}
      />
      <Tab.Screen 
        name="Outbreak" 
        component={OutbreakRadarScreen} 
        options={{ 
          title: 'Outbreak',
          tabBarIcon: ({ focused, size }) => (
            <Ionicons 
              name={focused ? "warning" : "warning-outline"} 
              size={size} 
              color={focused ? "#C62828" : "#78716c"} 
            />
          ),
          tabBarActiveTintColor: '#C62828',
        }}
      />
      <Tab.Screen 
        name="Assistant" 
        component={AssistantScreen} 
        options={{ 
          title: 'Assistant',
          tabBarIcon: ({ color, size }) => (
            <MaterialIcons name="psychology" size={size} color={color} />
          ),
          tabBarActiveTintColor: theme.colors.primary,
        }}
      />
      <Tab.Screen 
        name="Settings" 
        component={SettingsScreen} 
        options={{
          tabBarIcon: ({ color, size }) => (
            <MaterialIcons name="settings" size={size} color={color} />
          ),
          tabBarActiveTintColor: theme.colors.primary,
        }}
      />
    </Tab.Navigator>
  );
}

const styles = StyleSheet.create({
  tabBar: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    elevation: 0,
    backgroundColor: '#ffffff',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    height: Platform.OS === 'ios' ? 90 : 70,
    paddingBottom: Platform.OS === 'ios' ? 30 : 10,
    paddingTop: 10,
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: -4,
    },
    shadowOpacity: 0.05,
    shadowRadius: 10,
    borderTopWidth: 0,
  },
  iconContainer: {
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
    minWidth: 48,
  },
  iconContainerActive: {
    backgroundColor: 'rgba(13, 99, 27, 0.08)', 
  },
  tabLabel: {
    fontFamily: Platform.OS === 'android' ? 'sans-serif' : 'System',
    fontSize: 10,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginTop: 2,
  }
});
