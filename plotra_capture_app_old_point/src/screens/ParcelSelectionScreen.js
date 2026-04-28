import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { farmAPI } from '../services/api';

const ParcelSelectionScreen = ({ route, navigation }) => {
  const { farm } = route.params;
  const [parcels, setParcels] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadParcels();
  }, [farm.id]);

  const loadParcels = async () => {
    try {
      const response = await farmAPI.getParcels(farm.id);
      setParcels(response.data || []);
    } catch (error) {
      console.error('Error loading parcels:', error);
      Alert.alert('Error', 'Failed to load parcels');
      navigation.goBack();
    } finally {
      setIsLoading(false);
    }
  };

  const selectParcel = (parcel) => {
    // Navigate to capture screen with selected parcel
    navigation.navigate('Capture', {
      farm,
      parcel,
    });
  };

  const skipParcel = () => {
    // Navigate without selecting parcel (auto-detect)
    navigation.navigate('Capture', {
      farm,
      parcel: null,
    });
  };

  const renderParcelItem = ({ item }) => {
    const parcelName = item.name || `Parcel ${item.parcel_number}`;
    const area = item.area_hectares?.toFixed(2) || '0.00';

    return (
      <TouchableOpacity
        style={styles.card}
        onPress={() => selectParcel(item)}
      >
        <View style={styles.cardContent}>
          <View style={styles.headerRow}>
            <Text style={styles.parcelNumber}>#{item.parcel_number}</Text>
            <Text style={styles.areaBadge}>{area} ha</Text>
          </View>
          <Text style={styles.parcelName} numberOfLines={2}>
            {parcelName}
          </Text>
          {item.has_boundary ? (
            <View style={styles.boundaryIndicator}>
              <Text style={styles.boundaryText}>Boundary mapped</Text>
            </View>
          ) : (
            <View style={[styles.boundaryIndicator, styles.noBoundary]}>
              <Text style={[styles.boundaryText, styles.noBoundaryText]}>
                No boundary
              </Text>
            </View>
          )}
        </View>
      </TouchableOpacity>
    );
  };

  if (isLoading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#6f4e37" />
        <Text style={styles.loadingText}>Loading parcels...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Select Parcel</Text>
        <Text style={styles.subtitle}>
          {farm.farm_name || `Farm #${farm.id}`}
        </Text>
      </View>

      {parcels.length === 0 ? (
        <View style={styles.emptyContainer}>
          <Text style={styles.emptyTitle}>No Parcels Found</Text>
          <Text style={styles.emptyText}>
            This farm has no registered parcels.
            Capture will try to auto-detect the parcel from boundary data.
          </Text>
        </View>
      ) : (
        <FlatList
          data={parcels}
          renderItem={renderParcelItem}
          keyExtractor={(item) => `parcel-${item.id}`}
          contentContainerStyle={styles.list}
        />
      )}

      <TouchableOpacity style={styles.skipButton} onPress={skipParcel}>
        <Text style={styles.skipButtonText}>Skip - Capture without parcel</Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  header: {
    padding: 20,
    paddingTop: 60,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 16,
    color: '#666',
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
  list: {
    padding: 16,
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: 10,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
    elevation: 2,
  },
  cardContent: {
    padding: 16,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  parcelNumber: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#6f4e37',
  },
  areaBadge: {
    backgroundColor: '#e8f5e9',
    color: '#2e7d32',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
    fontSize: 12,
    fontWeight: '600',
  },
  parcelName: {
    fontSize: 14,
    color: '#555',
    marginBottom: 8,
  },
  boundaryIndicator: {
    alignSelf: 'flex-start',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
    backgroundColor: '#e3f2fd',
  },
  boundaryText: {
    fontSize: 12,
    color: '#1976d2',
  },
  noBoundary: {
    backgroundColor: '#ffebee',
  },
  noBoundaryText: {
    color: '#c62828',
  },
  skipButton: {
    margin: 16,
    paddingVertical: 14,
    borderRadius: 8,
    borderWidth: 2,
    borderColor: '#6f4e37',
    alignItems: 'center',
  },
  skipButtonText: {
    color: '#6f4e37',
    fontSize: 16,
    fontWeight: '600',
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 40,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 12,
  },
  emptyText: {
    fontSize: 16,
    color: '#666',
    textAlign: 'center',
    lineHeight: 24,
  },
});

export default ParcelSelectionScreen;
