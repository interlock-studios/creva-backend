# Flutter Integration Guide

This guide shows how to integrate the TikTok Workout Parser API with your Flutter app.

## How the API Works

The API has two response types:

1. **Instant Response** (when video is cached) - Returns workout JSON immediately
2. **Queued Response** (when video needs processing) - Returns job ID to check later

## Flutter Implementation

### 1. API Service Class

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class WorkoutApiService {
  final String baseUrl;
  final Duration pollingInterval;
  
  WorkoutApiService({
    required this.baseUrl,
    this.pollingInterval = const Duration(seconds: 2),
  });

  /// Process a TikTok video URL
  Future<WorkoutData> processVideo(String tiktokUrl) async {
    // Step 1: Submit video for processing
    final response = await http.post(
      Uri.parse('$baseUrl/process'),
      headers: {'Content-Type': 'application/json'},
      body: json.encode({'url': tiktokUrl}),
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to process video: ${response.body}');
    }

    final data = json.decode(response.body);

    // Check if we got instant result (cached)
    if (data['status'] == null) {
      // This is the workout data, return immediately
      return WorkoutData.fromJson(data);
    }

    // Otherwise, it's queued - poll for result
    if (data['status'] == 'queued' || data['status'] == 'processing') {
      final jobId = data['job_id'];
      return await _pollForResult(jobId);
    }

    throw Exception('Unexpected response: ${response.body}');
  }

  /// Poll for job completion
  Future<WorkoutData> _pollForResult(String jobId) async {
    const maxAttempts = 60; // 2 minutes max wait
    int attempts = 0;

    while (attempts < maxAttempts) {
      await Future.delayed(pollingInterval);
      
      final response = await http.get(
        Uri.parse('$baseUrl/status/$jobId'),
      );

      if (response.statusCode != 200) {
        throw Exception('Failed to check status: ${response.body}');
      }

      final data = json.decode(response.body);
      
      switch (data['status']) {
        case 'completed':
          return WorkoutData.fromJson(data['result']);
        
        case 'failed':
          throw Exception('Processing failed: ${data['last_error']}');
        
        case 'processing':
        case 'pending':
          // Continue polling
          attempts++;
          break;
          
        default:
          throw Exception('Unknown status: ${data['status']}');
      }
    }

    throw Exception('Timeout waiting for video processing');
  }
}
```

### 2. Data Models

```dart
class WorkoutData {
  final String title;
  final String? description;
  final String workoutType;
  final int? durationMinutes;
  final int difficultyLevel;
  final List<Exercise> exercises;
  final List<String>? tags;
  final String? creator;

  WorkoutData({
    required this.title,
    this.description,
    required this.workoutType,
    this.durationMinutes,
    required this.difficultyLevel,
    required this.exercises,
    this.tags,
    this.creator,
  });

  factory WorkoutData.fromJson(Map<String, dynamic> json) {
    return WorkoutData(
      title: json['title'],
      description: json['description'],
      workoutType: json['workout_type'],
      durationMinutes: json['duration_minutes'],
      difficultyLevel: json['difficulty_level'],
      exercises: (json['exercises'] as List)
          .map((e) => Exercise.fromJson(e))
          .toList(),
      tags: json['tags']?.cast<String>(),
      creator: json['creator'],
    );
  }
}

class Exercise {
  final String name;
  final List<String> muscleGroups;
  final String equipment;
  final List<ExerciseSet> sets;
  final String? instructions;

  Exercise({
    required this.name,
    required this.muscleGroups,
    required this.equipment,
    required this.sets,
    this.instructions,
  });

  factory Exercise.fromJson(Map<String, dynamic> json) {
    return Exercise(
      name: json['name'],
      muscleGroups: List<String>.from(json['muscle_groups']),
      equipment: json['equipment'],
      sets: (json['sets'] as List)
          .map((s) => ExerciseSet.fromJson(s))
          .toList(),
      instructions: json['instructions'],
    );
  }
}

class ExerciseSet {
  final int? reps;
  final double? weightLbs;
  final int? durationSeconds;
  final double? distanceMiles;
  final int? restSeconds;

  ExerciseSet({
    this.reps,
    this.weightLbs,
    this.durationSeconds,
    this.distanceMiles,
    this.restSeconds,
  });

  factory ExerciseSet.fromJson(Map<String, dynamic> json) {
    return ExerciseSet(
      reps: json['reps'],
      weightLbs: json['weight_lbs']?.toDouble(),
      durationSeconds: json['duration_seconds'],
      distanceMiles: json['distance_miles']?.toDouble(),
      restSeconds: json['rest_seconds'],
    );
  }
}
```

### 3. UI Implementation with Loading States

```dart
import 'package:flutter/material.dart';

class WorkoutProcessorScreen extends StatefulWidget {
  @override
  _WorkoutProcessorScreenState createState() => _WorkoutProcessorScreenState();
}

class _WorkoutProcessorScreenState extends State<WorkoutProcessorScreen> {
  final _urlController = TextEditingController();
  final _apiService = WorkoutApiService(
    baseUrl: 'https://your-api-url.run.app',
  );
  
  bool _isLoading = false;
  String? _statusMessage;
  WorkoutData? _workoutData;
  String? _errorMessage;

  Future<void> _processVideo() async {
    setState(() {
      _isLoading = true;
      _statusMessage = 'Processing video...';
      _errorMessage = null;
      _workoutData = null;
    });

    try {
      final workout = await _apiService.processVideo(_urlController.text);
      
      setState(() {
        _workoutData = workout;
        _isLoading = false;
        _statusMessage = null;
      });
    } catch (e) {
      setState(() {
        _errorMessage = e.toString();
        _isLoading = false;
        _statusMessage = null;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('TikTok Workout Parser'),
      ),
      body: Padding(
        padding: EdgeInsets.all(16.0),
        child: Column(
          children: [
            TextField(
              controller: _urlController,
              decoration: InputDecoration(
                labelText: 'TikTok URL',
                hintText: 'https://www.tiktok.com/@user/video/...',
              ),
            ),
            SizedBox(height: 16),
            ElevatedButton(
              onPressed: _isLoading ? null : _processVideo,
              child: Text('Process Video'),
            ),
            SizedBox(height: 24),
            if (_isLoading)
              Column(
                children: [
                  CircularProgressIndicator(),
                  SizedBox(height: 16),
                  Text(_statusMessage ?? 'Processing...'),
                ],
              ),
            if (_errorMessage != null)
              Card(
                color: Colors.red.shade100,
                child: Padding(
                  padding: EdgeInsets.all(16),
                  child: Text(
                    _errorMessage!,
                    style: TextStyle(color: Colors.red),
                  ),
                ),
              ),
            if (_workoutData != null)
              Expanded(
                child: WorkoutDetailsWidget(workout: _workoutData!),
              ),
          ],
        ),
      ),
    );
  }
}

class WorkoutDetailsWidget extends StatelessWidget {
  final WorkoutData workout;

  const WorkoutDetailsWidget({Key? key, required this.workout}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return ListView(
      children: [
        Card(
          child: Padding(
            padding: EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  workout.title,
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                if (workout.description != null)
                  Text(workout.description!),
                SizedBox(height: 8),
                Row(
                  children: [
                    Chip(label: Text(workout.workoutType)),
                    SizedBox(width: 8),
                    Chip(label: Text('Difficulty: ${workout.difficultyLevel}/10')),
                    if (workout.durationMinutes != null)
                      Padding(
                        padding: EdgeInsets.only(left: 8),
                        child: Chip(label: Text('${workout.durationMinutes} min')),
                      ),
                  ],
                ),
              ],
            ),
          ),
        ),
        ...workout.exercises.map((exercise) => ExerciseCard(exercise: exercise)),
      ],
    );
  }
}

class ExerciseCard extends StatelessWidget {
  final Exercise exercise;

  const ExerciseCard({Key? key, required this.exercise}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.symmetric(vertical: 8),
      child: Padding(
        padding: EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              exercise.name,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            SizedBox(height: 8),
            Wrap(
              spacing: 8,
              children: [
                ...exercise.muscleGroups.map((muscle) => 
                  Chip(
                    label: Text(muscle),
                    backgroundColor: Colors.blue.shade100,
                  )
                ),
                Chip(
                  label: Text(exercise.equipment),
                  backgroundColor: Colors.green.shade100,
                ),
              ],
            ),
            if (exercise.instructions != null)
              Padding(
                padding: EdgeInsets.only(top: 8),
                child: Text(exercise.instructions!),
              ),
            SizedBox(height: 8),
            ...exercise.sets.asMap().entries.map((entry) {
              final index = entry.key;
              final set = entry.value;
              return Padding(
                padding: EdgeInsets.only(top: 4),
                child: Text(
                  'Set ${index + 1}: ${_formatSet(set)}',
                  style: TextStyle(fontWeight: FontWeight.w500),
                ),
              );
            }),
          ],
        ),
      ),
    );
  }

  String _formatSet(ExerciseSet set) {
    final parts = <String>[];
    if (set.reps != null) parts.add('${set.reps} reps');
    if (set.weightLbs != null) parts.add('${set.weightLbs} lbs');
    if (set.durationSeconds != null) parts.add('${set.durationSeconds}s');
    if (set.distanceMiles != null) parts.add('${set.distanceMiles} miles');
    if (set.restSeconds != null) parts.add('Rest: ${set.restSeconds}s');
    return parts.join(', ');
  }
}
```

### 4. Advanced Features

#### Progress Indicator with Queue Position

```dart
class ProcessingStatus {
  final String status;
  final int? queuePosition;
  final String? estimatedTime;

  ProcessingStatus({
    required this.status,
    this.queuePosition,
    this.estimatedTime,
  });
}

// Add this method to your API service
Stream<ProcessingStatus> processVideoWithProgress(String tiktokUrl) async* {
  // Submit for processing
  final response = await http.post(
    Uri.parse('$baseUrl/process'),
    headers: {'Content-Type': 'application/json'},
    body: json.encode({'url': tiktokUrl}),
  );

  final data = json.decode(response.body);

  // If cached, return immediately
  if (data['status'] == null) {
    yield ProcessingStatus(status: 'completed');
    return;
  }

  // Poll for updates
  final jobId = data['job_id'];
  
  while (true) {
    await Future.delayed(pollingInterval);
    
    final statusResponse = await http.get(
      Uri.parse('$baseUrl/status/$jobId'),
    );
    
    final statusData = json.decode(statusResponse.body);
    
    yield ProcessingStatus(
      status: statusData['status'],
      queuePosition: statusData['queue_position'],
      estimatedTime: statusData['estimated_time'],
    );
    
    if (statusData['status'] == 'completed' || 
        statusData['status'] == 'failed') {
      break;
    }
  }
}
```

#### Error Handling with Retry

```dart
class ApiException implements Exception {
  final int statusCode;
  final String message;
  
  ApiException(this.statusCode, this.message);
  
  bool get isRetryable => statusCode >= 500 || statusCode == 429;
}

Future<T> retryableApiCall<T>(
  Future<T> Function() apiCall, {
  int maxRetries = 3,
  Duration initialDelay = const Duration(seconds: 1),
}) async {
  int attempts = 0;
  Duration delay = initialDelay;
  
  while (attempts < maxRetries) {
    try {
      return await apiCall();
    } on ApiException catch (e) {
      attempts++;
      
      if (!e.isRetryable || attempts >= maxRetries) {
        rethrow;
      }
      
      await Future.delayed(delay);
      delay *= 2; // Exponential backoff
    }
  }
  
  throw Exception('Max retries exceeded');
}
```

## Best Practices

### 1. Cache Results Locally

```dart
import 'package:shared_preferences/shared_preferences.dart';

class WorkoutCache {
  static const _cachePrefix = 'workout_';
  static const _cacheExpiry = Duration(hours: 24);
  
  final SharedPreferences _prefs;
  
  WorkoutCache(this._prefs);
  
  Future<void> saveWorkout(String url, WorkoutData workout) async {
    final key = '$_cachePrefix${url.hashCode}';
    final data = {
      'workout': workout.toJson(),
      'timestamp': DateTime.now().toIso8601String(),
    };
    await _prefs.setString(key, json.encode(data));
  }
  
  WorkoutData? getWorkout(String url) {
    final key = '$_cachePrefix${url.hashCode}';
    final dataStr = _prefs.getString(key);
    
    if (dataStr == null) return null;
    
    final data = json.decode(dataStr);
    final timestamp = DateTime.parse(data['timestamp']);
    
    // Check if expired
    if (DateTime.now().difference(timestamp) > _cacheExpiry) {
      _prefs.remove(key);
      return null;
    }
    
    return WorkoutData.fromJson(data['workout']);
  }
}
```

### 2. Handle Network Issues Gracefully

```dart
class NetworkAwareApiService extends WorkoutApiService {
  final Connectivity connectivity;
  
  NetworkAwareApiService({
    required String baseUrl,
    required this.connectivity,
  }) : super(baseUrl: baseUrl);
  
  @override
  Future<WorkoutData> processVideo(String tiktokUrl) async {
    // Check network first
    final connectivityResult = await connectivity.checkConnectivity();
    if (connectivityResult == ConnectivityResult.none) {
      throw Exception('No internet connection');
    }
    
    try {
      return await super.processVideo(tiktokUrl);
    } on SocketException {
      throw Exception('Network error. Please check your connection.');
    } on TimeoutException {
      throw Exception('Request timed out. Please try again.');
    }
  }
}
```

### 3. URL Validation

```dart
bool isValidTikTokUrl(String url) {
  final regex = RegExp(
    r'^https?://(www\.)?(tiktok\.com/@[\w.-]+/video/\d+|vm\.tiktok\.com/[\w-]+)',
    caseSensitive: false,
  );
  return regex.hasMatch(url);
}

// Use in your UI
if (!isValidTikTokUrl(_urlController.text)) {
  setState(() {
    _errorMessage = 'Please enter a valid TikTok video URL';
  });
  return;
}
```

## Testing

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';

class MockWorkoutApiService extends Mock implements WorkoutApiService {}

void main() {
  group('WorkoutApiService', () {
    test('handles cached response correctly', () async {
      final mockApi = MockWorkoutApiService();
      final cachedResponse = {
        'title': 'Test Workout',
        'workout_type': 'strength',
        'difficulty_level': 5,
        'exercises': [],
      };
      
      when(mockApi.processVideo(any))
          .thenAnswer((_) async => WorkoutData.fromJson(cachedResponse));
      
      final result = await mockApi.processVideo('https://tiktok.com/test');
      expect(result.title, 'Test Workout');
    });
    
    test('handles queued response with polling', () async {
      // Test implementation
    });
  });
}
```

## Summary

The API intelligently handles both instant (cached) and queued responses:

- **Cached videos**: Return workout data immediately (90% of popular videos)
- **New videos**: Queue for processing and poll for results
- **Failed processing**: Automatic retries with clear error messages

This provides the best user experience - instant results when possible, with reliable processing for new content.