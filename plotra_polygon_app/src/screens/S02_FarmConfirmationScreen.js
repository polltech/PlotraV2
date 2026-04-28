import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Image,
  Alert,
} from 'react-native';
import { useRoute, useNavigation } from '@react-navigation/native';
import * as Network from 'expo-network';

const FarmConfirmationScreen = () => {
  const route = useRoute();
  const navigation = useNavigation();
  const { farmId, farm } = route.params || {};

  const [isOnline, setIsOnline] = useState(true);
  const [farmDetails, setFarmDetails] = useState(farm || null);
  const [loading, setLoading] = useState(!farm);

  useEffect(() => {
    checkConnectivity();
    if (!farm) fetchFarmDetails();
  }, []);

  const checkConnectivity = async () => {
    const state = await Network.getNetworkStateAsync();
    setIsOnline(state.isConnected);
  };

  const fetchFarmDetails = async () => {
    try {
      // URS: GET /api/v1/farms/{farm_id} with API key header
      const response = await fetch(
        `http://192.168.100.5:8000/api/v1/farms/${encodeURIComponent(farmId)}`,
        {
          headers: {
            'X-API-Key': 'plotra-prototype-key-2026',
          },
        }
      );
      if (response.ok) {
        const data = await response.json();
        setFarmDetails(data);
      } else {
        setFarmDetails({ farm_id: farmId, farm_name: `Farm ${farmId}` });
      }
    } catch (error) {
      setFarmDetails({ farm_id: farmId, farm_name: `Farm ${farmId}` });
    } finally {
      setLoading(false);
    }
  };

  const handleProceed = () => {
    navigation.navigate('WalkBoundary', { farmId, farm: farmDetails });
  };

  const handleBack = () => {
    navigation.goBack();
  };

  if (loading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#6f4e37" />
        <Text style={styles.loadingText}>Loading farm details...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={handleBack}>
          <Text style={styles.backText}>‹ Back</Text>
        </TouchableOpacity>
        <Text style={styles.title}>Confirm farm</Text>
        <View style={{ width: 60 }} />
      </View>

      <ScrollView style={styles.content}>
        <View style={styles.card}>
          <View style={styles.row}>
            <Text style={styles.label}>Farm ID</Text>
            <Text style={styles.value}>{farmId}</Text>
          </View>

          {farmDetails?.farm_name && (
            <View style={styles.row}>
              <Text style={styles.label}>Farm name</Text>
              <Text style={styles.value}>{farmDetails.farm_name}</Text>
            </View>
          )}

          {farmDetails?.cooperative_name && (
            <View style={styles.row}>
              <Text style={styles.label}>Cooperative</Text>
              <Text style={styles.value}>{farmDetails.cooperative_name}</Text>
            </View>
          )}

          {farmDetails?.total_area_hectares && (
            <View style={styles.row}>
              <Text style={styles.label}>Registered area</Text>
              <Text style={styles.value}>
                {farmDetails.total_area_hectares.toFixed(2)} ha
              </Text>
            </View>
          )}

          <View style={styles.noteBox}>
            <Text style={styles.noteText}>
              Check details match the farmer before proceeding
            </Text>
          </View>

          {!isOnline && (
            <View style={styles.offlineBanner}>
              <Text style={styles.offlineText}>⚠️ Offline mode — details may be outdated</Text>
            </View>
          )}
        </View>

        <TouchableOpacity style={styles.proceedButton} onPress={handleProceed}>
          <Text style={styles.proceedButtonText}>Start polygon walk →</Text>
        </TouchableOpacity>

        <Text style={styles.footer}>
          Wrong farm? Go back and enter a different ID.
        </Text>
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 12,
    color: '#666',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 20,
    paddingTop: 60,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  backText: {
    fontSize: 18,
    color: '#6f4e37',
    fontWeight: '600',
  },
  title: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
  },
  content: {
    flex: 1,
    padding: 16,
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginBottom: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  row: {
    marginBottom: 12,
  },
  label: {
    fontSize: 12,
    color: '#666',
    marginBottom: 4,
    textTransform: 'uppercase',
  },
  value: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
  },
  noteBox: {
    marginTop: 16,
    padding: 12,
    backgroundColor: '#fff3e0',
    borderRadius: 8,
    borderLeftWidth: 4,
    borderLeftColor: '#ff9800',
  },
  noteText: {
    fontSize: 13,
    color: '#e65100',
    lineHeight: 18,
  },
  offlineBanner: {
    marginTop: 12,
    padding: 10,
    backgroundColor: '#ffebee',
    borderRadius: 6,
  },
  offlineText: {
    fontSize: 12,
    color: '#c62828',
    textAlign: 'center',
  },
  proceedButton: {
    backgroundColor: '#6f4e37',
    paddingVertical: 16,
    borderRadius: 8,
    alignItems: 'center',
  },
  proceedButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  footer: {
    marginTop: 16,
    textAlign: 'center',
    fontSize: 14,
    color: '#666',
    fontStyle: 'italic',
  },
});

export default FarmConfirmationScreen;
