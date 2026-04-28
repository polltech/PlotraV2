import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Alert,
  ScrollView,
  Platform,
  TextInput,
} from 'react-native';
import * as Location from 'expo-location';
import { captureAPI } from '../services/api';
import { MIN_ACCURACY_FOR_CAPTURE, GPS_ACCURACY_THRESHOLD } from '../config';

const CaptureScreen = ({ route, navigation }) => {
  const { farm, parcel } = route.params || {};
  const isFromParcelSelection = !!route.params;

  const [location, setLocation] = useState(null);
  const [locationError, setLocationError] = useState(null);
  const [isGettingLocation, setIsGettingLocation] = useState(false);
  const [isCapturing, setIsCapturing] = useState(false);
  const [captureResult, setCaptureResult] = useState(null);
  const [notes, setNotes] = useState('');

  // Location subscription
  const locationSubscription = useRef(null);
  const watchIdRef = useRef(null);

  // Request location permissions and start watching
  useEffect(() => {
    requestLocationPermission();
    startLocationWatch();

    return () => {
      stopLocationWatch();
    };
  }, []);

  const requestLocationPermission = async () => {
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        setLocationError('Location permission denied');
        Alert.alert('Permission Required', 'Please enable location services to capture GPS coordinates.');
        return;
      }
    } catch (error) {
      setLocationError('Failed to request location permission');
    }
  };

  const startLocationWatch = async () => {
    try {
      setIsGettingLocation(true);

      // Configure location options for high accuracy
      const locationOptions = {
        accuracy: Location.Accuracy.High,
        timeInterval: 1000,  // Update every second
        distanceInterval: 1, // Update every meter
        showsBackgroundLocationIndicator: false,
      };

      watchIdRef.current = await Location.watchPositionAsync(
        locationOptions,
        (newLocation) => {
          setLocation(newLocation);
          setLocationError(null);
        }
      );

    } catch (error) {
      console.error('Error watching location:', error);
      setLocationError('Failed to get GPS signal');
    } finally {
      setIsGettingLocation(false);
    }
  };

  const stopLocationWatch = () => {
    if (watchIdRef.current) {
      watchIdRef.current.remove();
      watchIdRef.current = null;
    }
  };

  const handleCapture = async () => {
    if (!location) {
      Alert.alert('No Location', 'Wait for GPS signal before capturing.');
      return;
    }

    const accuracy = location.coords.accuracy || location.accuracy;
    if (accuracy > MIN_ACCURACY_FOR_CAPTURE) {
      Alert.alert(
        'Low Accuracy',
        `GPS accuracy is ${accuracy.toFixed(1)}m. Move to an open area for better accuracy. Capture anyway?`,
        [
          { text: 'Cancel', style: 'cancel' },
          { text: 'Capture Anyway', onPress: performCapture },
        ]
      );
    } else {
      performCapture();
    }
  };

  const performCapture = async () => {
    setIsCapturing(true);
    try {
      const captureData = {
        farm_id: farm.id,
        parcel_id: parcel?.id || null,
        latitude: location.coords.latitude,
        longitude: location.coords.longitude,
        altitude: location.coords.altitude || null,
        accuracy_meters: location.coords.accuracy || location.accuracy || null,
        capture_method: 'phone_gps',
        device_model: `${Platform.OS} ${Platform.Version}`,
        app_version: '1.0.0',
        notes: notes.trim() || null,
        captured_at: new Date().toISOString(),
      };

      const response = await captureAPI.capture(captureData);
      setCaptureResult(response.data);
    } catch (error) {
      console.error('Capture error:', error);
      Alert.alert(
        'Capture Failed',
        error.response?.data?.detail || 'Failed to send capture. Please try again.'
      );
    } finally {
      setIsCapturing(false);
    }
  };

  const handleNewCapture = () => {
    setCaptureResult(null);
    setNotes('');
    // Could also navigate back to farm list
    if (isFromParcelSelection) {
      navigation.goBack();
    }
  };

  // Show loading while getting initial GPS
  if (isGettingLocation && !location) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#6f4e37" />
        <Text style={styles.statusText}>Acquiring GPS signal...</Text>
        <Text style={styles.hintText}>Move outdoors for better accuracy</Text>
      </View>
    );
  }

  // Show capture result
  if (captureResult) {
    return (
      <ScrollView style={styles.container}>
        <View style={styles.resultContainer}>
          <Text style={styles.resultTitle}>Analysis Complete</Text>

          {/* Status Card */}
          <View style={[
            styles.statusCard,
            captureResult.analysis?.risk_level === 'low' && styles.statusLow,
            captureResult.analysis?.risk_level === 'medium' && styles.statusMedium,
            captureResult.analysis?.risk_level === 'high' && styles.statusHigh,
          ]}>
            <Text style={styles.statusLabel}>Compliance Status</Text>
            <Text style={styles.statusValue}>
              {captureResult.analysis?.compliance_status || 'Unknown'}
            </Text>
            <Text style={styles.riskLevel}>
              Risk Level: {captureResult.analysis?.risk_level?.toUpperCase() || 'UNKNOWN'}
            </Text>
          </View>

          {/* Risk Score */}
          <View style={styles.scoreCard}>
            <Text style={styles.scoreLabel}>EUDR Risk Score</Text>
            <View style={styles.scoreCircle}>
              <Text style={[
                styles.scoreValue,
                captureResult.analysis?.risk_score < 30 && styles.scoreLow,
                captureResult.analysis?.risk_score >= 30 && captureResult.analysis?.risk_score < 70 && styles.scoreMedium,
                captureResult.analysis?.risk_score >= 70 && styles.scoreHigh,
              ]}>
                {captureResult.analysis?.risk_score?.toFixed(1) || '0.0'}%
              </Text>
            </View>
          </View>

          {/* Parcel Info */}
          {captureResult.parcel_info && (
            <View style={styles.infoCard}>
              <Text style={styles.infoTitle}>Parcel Detected</Text>
              <Text style={styles.infoValue}>
                {captureResult.parcel_info.name} (Parcel #{captureResult.parcel_info.parcel_number})
              </Text>
              <Text style={styles.infoSub}>Area: {captureResult.parcel_info.area_hectares?.toFixed(2)} ha</Text>
            </View>
          )}

          {/* Accuracy & Location */}
          <View style={styles.infoCard}>
            <Text style={styles.infoTitle}>Capture Details</Text>
            <Text style={styles.infoText}>
              Latitude: {captureResult.capture.latitude.toFixed(6)}{'\n'}
              Longitude: {captureResult.capture.longitude.toFixed(6)}{'\n'}
              Accuracy: {captureResult.capture.accuracy_meters?.toFixed(1) || 'N/A'} meters
            </Text>
          </View>

          {/* Recommendations */}
          {captureResult.recommendations && captureResult.recommendations.length > 0 && (
            <View style={styles.recommendationsCard}>
              <Text style={styles.recommendationsTitle}>Recommendations</Text>
              {captureResult.recommendations.map((rec, index) => (
                <View key={index} style={styles.recommendationItem}>
                  <Text style={styles.bullet}>•</Text>
                  <Text style={styles.recommendationText}>{rec}</Text>
                </View>
              ))}
            </View>
          )}

          <TouchableOpacity style={styles.newCaptureButton} onPress={handleNewCapture}>
            <Text style={styles.newCaptureButtonText}>New Capture</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    );
  }

  // Main capture screen
  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>GPS Capture</Text>
        <Text style={styles.subtitle}>
          {farm.farm_name || `Farm #${farm.id}`}
          {parcel && ` • Parcel #${parcel.parcel_number}`}
        </Text>
      </View>

      <ScrollView style={styles.content}>
        {/* GPS Status */}
        <View style={styles.statusCard}>
          <Text style={styles.statusLabel}>GPS Signal</Text>
          {location ? (
            <>
              <View style={styles.gpsInfoRow}>
                <View style={[
                  styles.accuracyDot,
                  (location.coords.accuracy || location.accuracy) <= GPS_ACCURACY_THRESHOLD
                    ? styles.accuracyGood
                    : styles.accuracyPoor
                ]} />
                <Text style={styles.gpsInfoText}>
                  Accuracy: {(location.coords.accuracy || location.accuracy).toFixed(1)}m
                </Text>
              </View>
              <Text style={styles.coordsText}>
                Lat: {location.coords.latitude.toFixed(6)}{'\n'}
                Lon: {location.coords.longitude.toFixed(6)}
              </Text>
              {location.coords.altitude && (
                <Text style={styles.coordsText}>
                  Altitude: {location.coords.altitude.toFixed(1)}m
                </Text>
              )}
            </>
          ) : (
            <Text style={styles.errorText}>
              {locationError || 'Waiting for GPS signal...'}
            </Text>
          )}
        </View>

        {/* Notes input */}
        <View style={styles.notesCard}>
          <Text style={styles.notesLabel}>Field Notes (optional)</Text>
          <TextInput
            style={styles.notesInput}
            value={notes}
            onChangeText={setNotes}
            placeholder="Add any observations..."
            placeholderTextColor="#999"
            multiline
            numberOfLines={3}
          />
        </View>

        {/* Capture Button */}
        <TouchableOpacity
          style={[
            styles.captureButton,
            (!location || isCapturing) && styles.captureButtonDisabled,
          ]}
          onPress={handleCapture}
          disabled={!location || isCapturing}
        >
          {isCapturing ? (
            <ActivityIndicator size="large" color="#fff" />
          ) : (
            <>
              <Text style={styles.captureButtonIcon}>📍</Text>
              <Text style={styles.captureButtonText}>Capture & Analyze</Text>
              <Text style={styles.captureButtonSub}>
                Sends GPS to server for instant EUDR analysis
              </Text>
            </>
          )}
        </TouchableOpacity>

        <Text style={styles.disclaimer}>
          By capturing, you confirm this location is accurate to the best of your knowledge.
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
  header: {
    padding: 20,
    paddingTop: 60,
    backgroundColor: '#6f4e37',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.8)',
  },
  content: {
    flex: 1,
    padding: 16,
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 40,
  },
  statusText: {
    marginTop: 16,
    fontSize: 16,
    color: '#333',
  },
  hintText: {
    marginTop: 8,
    fontSize: 14,
    color: '#666',
  },
  statusCard: {
    backgroundColor: '#fff',
    padding: 16,
    borderRadius: 10,
    marginBottom: 16,
    borderLeftWidth: 4,
    borderLeftColor: '#4caf50',
  },
  statusLabel: {
    fontSize: 12,
    color: '#666',
    fontWeight: '600',
    marginBottom: 8,
    textTransform: 'uppercase',
  },
  gpsInfoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  accuracyDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    marginRight: 8,
  },
  accuracyGood: {
    backgroundColor: '#4caf50',
  },
  accuracyPoor: {
    backgroundColor: '#f44336',
  },
  gpsInfoText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
  },
  coordsText: {
    fontSize: 13,
    color: '#666',
    marginTop: 4,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  errorText: {
    fontSize: 14,
    color: '#f44336',
    fontStyle: 'italic',
  },
  notesCard: {
    backgroundColor: '#fff',
    padding: 16,
    borderRadius: 10,
    marginBottom: 16,
  },
  notesLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
    marginBottom: 8,
  },
  notesInput: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 12,
    fontSize: 14,
    color: '#333',
    textAlignVertical: 'top',
    minHeight: 80,
  },
  captureButton: {
    backgroundColor: '#4caf50',
    paddingVertical: 20,
    borderRadius: 12,
    alignItems: 'center',
    marginBottom: 16,
  },
  captureButtonDisabled: {
    backgroundColor: '#ccc',
  },
  captureButtonIcon: {
    fontSize: 32,
    marginBottom: 4,
  },
  captureButtonText: {
    color: '#fff',
    fontSize: 18,
    fontWeight: 'bold',
  },
  captureButtonSub: {
    color: 'rgba(255,255,255,0.8)',
    fontSize: 12,
    marginTop: 4,
  },
  disclaimer: {
    fontSize: 12,
    color: '#999',
    textAlign: 'center',
    fontStyle: 'italic',
    lineHeight: 18,
  },
  resultContainer: {
    padding: 16,
  },
  resultTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 20,
    textAlign: 'center',
  },
  statusCard: {
    padding: 20,
    borderRadius: 12,
    marginBottom: 16,
    borderLeftWidth: 6,
  },
  statusLow: {
    borderLeftColor: '#4caf50',
    backgroundColor: '#e8f5e9',
  },
  statusMedium: {
    borderLeftColor: '#ff9800',
    backgroundColor: '#fff3e0',
  },
  statusHigh: {
    borderLeftColor: '#f44336',
    backgroundColor: '#ffebee',
  },
  statusLabel: {
    fontSize: 12,
    color: '#666',
    fontWeight: '600',
    marginBottom: 8,
  },
  statusValue: {
    fontSize: 22,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 4,
  },
  riskLevel: {
    fontSize: 14,
    color: '#666',
    fontWeight: '500',
  },
  scoreCard: {
    backgroundColor: '#fff',
    padding: 20,
    borderRadius: 12,
    alignItems: 'center',
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#e0e0e0',
  },
  scoreLabel: {
    fontSize: 14,
    color: '#666',
    fontWeight: '600',
    marginBottom: 12,
  },
  scoreCircle: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: '#f5f5f5',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 4,
    borderColor: '#6f4e37',
  },
  scoreValue: {
    fontSize: 28,
    fontWeight: 'bold',
  },
  scoreLow: {
    color: '#4caf50',
  },
  scoreMedium: {
    color: '#ff9800',
  },
  scoreHigh: {
    color: '#f44336',
  },
  infoCard: {
    backgroundColor: '#fff',
    padding: 16,
    borderRadius: 10,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#e0e0e0',
  },
  infoTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#666',
    marginBottom: 6,
  },
  infoValue: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  infoSub: {
    fontSize: 14,
    color: '#666',
  },
  infoText: {
    fontSize: 14,
    color: '#333',
    lineHeight: 22,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  recommendationsCard: {
    backgroundColor: '#e3f2fd',
    padding: 16,
    borderRadius: 10,
    marginBottom: 20,
  },
  recommendationsTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#1976d2',
    marginBottom: 12,
  },
  recommendationItem: {
    flexDirection: 'row',
    marginBottom: 8,
  },
  bullet: {
    color: '#1976d2',
    marginRight: 8,
    fontSize: 16,
  },
  recommendationText: {
    flex: 1,
    fontSize: 14,
    color: '#333',
    lineHeight: 20,
  },
  newCaptureButton: {
    backgroundColor: '#6f4e37',
    paddingVertical: 16,
    borderRadius: 10,
    alignItems: 'center',
  },
  newCaptureButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
});

export default CaptureScreen;
