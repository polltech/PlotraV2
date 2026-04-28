import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import * as Network from 'expo-network';
import AsyncStorage from '@react-native-async-storage/async-storage';

const FarmIDEntryScreen = () => {
  const [farmId, setFarmId] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const navigation = useNavigation();

  useEffect(() => {
    // Check connectivity on mount
    checkConnection();
  }, []);

  const checkConnection = async () => {
    const networkState = await Network.getNetworkStateAsync();
    return networkState.isConnected;
  };

  const handleContinue = async () => {
    if (!farmId.trim()) {
      Alert.alert('Error', 'Farm ID is required');
      return;
    }

    setIsLoading(true);
    try {
      // If online, fetch farm details
      const isConnected = await checkConnection();
      if (isConnected) {
        // Fetch from API
        const response = await fetch(
          `http://192.168.100.5:8000/api/v2/farmer/farm?farm_id=${encodeURIComponent(farmId)}`
        );
        if (response.ok) {
          const farmData = await response.json();
          navigation.navigate('FarmConfirmation', { farm: farmData });
          return;
        }
      }

      // Offline or fetch failed: proceed to map anyway (user can enter manually)
      navigation.navigate('WalkBoundary', { farmId: farmId.trim() });
    } catch (error) {
      // Offline or error — proceed to map
      navigation.navigate('WalkBoundary', { farmId: farmId.trim() });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <View style={styles.content}>
        <View style={styles.header}>
          <Text style={styles.logo}>Plotra Field</Text>
          <Text style={styles.title}>Start Polygon Capture</Text>
          <Text style={styles.subtitle}>
            Enter the Farm ID from the Plotra web portal
          </Text>
        </View>

        <View style={styles.form}>
          <View style={styles.inputGroup}>
            <Text style={styles.label}>Farm ID / Code</Text>
            <TextInput
              style={[styles.input, styles.inputError]}
              value={farmId}
              onChangeText={setFarmId}
              placeholder="e.g., KE-NYR-00412"
              placeholderTextColor="#999"
              autoCapitalize="characters"
              testID="farm-id-input"
              accessibilityLabel="Farm ID input"
            />
            <Text style={styles.hint}>As shown on the farmer record in Plotra</Text>
          </View>

          {!farmId.trim() && (
            <Text style={styles.errorText}>Farm ID required</Text>
          )}

          <TouchableOpacity
            style={[
              styles.button,
              (!farmId.trim() || isLoading) && styles.buttonDisabled
            ]}
            onPress={handleContinue}
            disabled={!farmId.trim() || isLoading}
          >
            {isLoading ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <>
                <Text style={styles.buttonText}>Confirm Farm ID →</Text>
                <Text style={styles.buttonSub}>View queued records</Text>
              </>
            )}
          </TouchableOpacity>
        </View>
      </View>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  content: {
    flex: 1,
    justifyContent: 'center',
    padding: 20,
  },
  header: {
    alignItems: 'center',
    marginBottom: 40,
  },
  logo: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#6f4e37',
    marginBottom: 8,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 8,
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 14,
    color: '#666',
    textAlign: 'center',
    lineHeight: 20,
  },
  form: {
    backgroundColor: '#fff',
    padding: 20,
    borderRadius: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  inputGroup: {
    marginBottom: 20,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
    marginBottom: 8,
  },
  input: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 14,
    fontSize: 16,
    color: '#333',
  },
  inputError: {
    borderColor: '#f44336',
  },
  hint: {
    fontSize: 12,
    color: '#999',
    marginTop: 6,
  },
  errorText: {
    fontSize: 12,
    color: '#f44336',
    marginBottom: 12,
    marginTop: -8,
  },
  button: {
    backgroundColor: '#6f4e37',
    paddingVertical: 16,
    borderRadius: 8,
    alignItems: 'center',
  },
  buttonDisabled: {
    backgroundColor: '#ccc',
  },
  buttonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  buttonSub: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.8)',
    marginTop: 2,
  },
});

export default FarmIDEntryScreen;
