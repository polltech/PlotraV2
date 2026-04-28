import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { useAuth } from '../context/AuthContext';

// Screens (import them)
import FarmIDEntryScreen from '../screens/S01_FarmIDEntryScreen';
import FarmConfirmationScreen from '../screens/S02_FarmConfirmationScreen';
import WalkBoundaryScreen from '../screens/S03_WalkBoundaryScreen';
import ReviewPolygonScreen from '../screens/S05_ReviewPolygonScreen';
import OfflineSavedScreen from '../screens/S06_OfflineSavedScreen';
import SubmittedScreen from '../screens/S07_SubmittedScreen';
import QueueListScreen from '../screens/S08_QueueListScreen';

const Stack = createNativeStackNavigator();

const AppNavigator = () => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    // Could render splash
    return null;
  }

  return (
    <NavigationContainer>
      <Stack.Navigator
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: '#f5f5f5' },
        }}
      >
        {!isAuthenticated ? (
          <>
            <Stack.Screen name="Login" component={LoginScreen} />
            <Stack.Screen name="Register" component={RegisterScreen} />
          </>
        ) : (
          <>
            <Stack.Screen name="FarmIDEntry" component={FarmIDEntryScreen} />
            <Stack.Screen
              name="FarmConfirmation"
              component={FarmConfirmationScreen}
              options={{
                headerShown: true,
                title: 'Confirm Farm',
                headerBackTitle: 'Back',
                headerTintColor: '#6f4e37',
              }}
            />
            <Stack.Screen
              name="WalkBoundary"
              component={WalkBoundaryScreen}
              options={{
                headerShown: false, // Custom top bar
              }}
            />
            <Stack.Screen
              name="ReviewPolygon"
              component={ReviewPolygonScreen}
              options={{
                headerShown: true,
                title: 'Review',
                headerBackTitle: 'Back',
                headerTintColor: '#6f4e37',
              }}
            />
            <Stack.Screen
              name="OfflineSaved"
              component={OfflineSavedScreen}
              options={{ headerShown: false }}
            />
            <Stack.Screen
              name="Submitted"
              component={SubmittedScreen}
              options={{ headerShown: false }}
            />
            <Stack.Screen
              name="QueueList"
              component={QueueListScreen}
              options={{
                headerShown: true,
                title: 'Queued Records',
                headerBackTitle: 'Home',
                headerTintColor: '#6f4e37',
              }}
            />
          </>
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
};

export default AppNavigator;
