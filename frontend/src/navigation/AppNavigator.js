import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { MaterialIcons } from '@expo/vector-icons';
import { getFocusedRouteNameFromRoute } from '@react-navigation/native';
import { View, StyleSheet, Platform } from 'react-native';

import { theme } from '../theme';

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
        tabBarIcon: ({ focused }) => {
          let iconName;
          if (route.name === 'Home') iconName = 'home';
          else if (route.name === 'Diagnose') iconName = 'photo-camera';
          else if (route.name === 'Market') iconName = 'storefront';
          else if (route.name === 'Settings') iconName = 'settings';
          
          return (
            <View style={[styles.iconContainer, focused && styles.iconContainerActive]}>
                <MaterialIcons name={iconName} size={22} color={focused ? theme.colors.primary : '#57534e'} />
            </View>
          );
        },
        tabBarActiveTintColor: theme.colors.primary,
        tabBarInactiveTintColor: '#78716c',
        headerShown: false,
        tabBarShowLabel: true,
        tabBarLabelStyle: styles.tabLabel,
        tabBarStyle: styles.tabBar,
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
            return styles.tabBar;
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
            return styles.tabBar;
          })(route),
        })}
      />
      <Tab.Screen name="Settings" component={SettingsScreen} />
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
