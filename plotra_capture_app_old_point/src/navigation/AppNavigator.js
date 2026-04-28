import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { useAuth } from '../context/AuthContext';
import LoginScreen from '../screens/LoginScreen';
import RegisterScreen from '../screens/RegisterScreen';
import FarmListScreen from '../screens/FarmListScreen';
import ParcelSelectionScreen from '../screens/ParcelSelectionScreen';
import CaptureScreen from '../screens/CaptureScreen';

const Stack = createNativeStackNavigator();

const AppNavigator = () => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    // Could return a splash screen here
    return null;
  }

  return (
    <NavigationContainer>
      <Stack.Navigator screenOptions={{ headerShown: false }}>
        {!isAuthenticated ? (
          // Auth screens
          <>
            <Stack.Screen name="Login" component={LoginScreen} />
            <Stack.Screen name="Register" component={RegisterScreen} />
          </>
        ) : (
          // Main app screens
          <>
            <Stack.Screen
              name="FarmList"
              component={FarmListScreen}
              options={{ headerShown: false }}
            />
            <Stack.Screen
              name="ParcelSelection"
              component={ParcelSelectionScreen}
              options={{
                headerShown: true,
                title: 'Select Parcel',
                headerBackTitle: 'Back',
              }}
            />
            <Stack.Screen
              name="Capture"
              component={CaptureScreen}
              options={{
                headerShown: true,
                title: 'Capture GPS',
                headerBackTitle: 'Back',
              }}
            />
          </>
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
};

export default AppNavigator;
