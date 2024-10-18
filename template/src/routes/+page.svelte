<script lang="ts">
	import { Button } from '$lib/components/ui/button/index';
	import * as Card from '$lib/components/ui/card/index';
	import { Label } from '$lib/components/ui/label';
	import Reload from 'svelte-radix/Reload.svelte';
	import { Separator } from '$lib/components/ui/separator/index.js';
	import { io, Socket } from 'socket.io-client';
	import * as Tabs from '$lib/components/ui/tabs/index.js';
	import * as RadioGroup from '$lib/components/ui/radio-group';
	import { onMount } from 'svelte';
	import {
		earthquakeExample1,
		earthquakeExample2,
		earthquakeExample3
	} from '$lib/earthquake-example/sample';

	let data: number[] = [];
	const samplingRate: number = 100; // 100 Hz means 100 samples per second
	const displayDuration = 10; // Display the last 10 seconds
	const maxDataPoints = samplingRate * displayDuration; // 100 samples/second * 10 seconds = 1000 samples
	const maxWaveformPoints = 60 * samplingRate; // 60 seconds
	let waveform: HTMLDivElement;
	let waveIndex = 0;
	let example = 'Example 1';
	let building_type = '3';

	function getHost() {
		return window.location.href;
	}

	function generateSeismicWave1(i: number) {
		if (example == 'Example 1') {
			return earthquakeExample1[i];
		} else if (example == 'Example 2') {
			return earthquakeExample2[i];
		}
		return earthquakeExample3[i];
	}

	let content: string | undefined =
		"<div style='color:grey'><strong>No earthquake detected so far!</strong>";
	let disabled = false;
	let buttonText = 'Simulate Earthquake';

	let socket: Socket;
	onMount(() => {
		let hostname = getHost();
		socket = io(hostname, {
			transports: ['websocket']
		});
		socket.on('connect', function () {
			console.log('Connect: Successfully connected to the server!');
		});
		socket.on('disconnect', function (reason) {
			console.log('Disconnect: ', reason);
		});
		socket.on('connect_error', (err) => {
			// the reason of the error, for example "xhr poll error"
			console.log('Error connect: ', err.message);
		});

		const handleBeforeUnload = (event: BeforeUnloadEvent) => {
			socket.disconnect();
			console.log('Disconnected from server');
		};

		window.addEventListener('beforeunload', handleBeforeUnload);

		return () => {
			window.removeEventListener('beforeunload', handleBeforeUnload);
		};
	});

	// Disconnect from server after 20 seconds
	$: if (waveIndex == 40 * samplingRate) {
		socket.disconnect();
	}

	async function analyseWave() {
		content = "<div style='color:grey'><strong>No earthquake detected so far!</strong>";
		disabled = true;
		const p5 = (await import('p5')).default; // Dynamically import P5.js

		// Stream data to the server every 0.01 seconds
		let waveSample: number = 0;
		let sendWave = setInterval(function () {
			waveSample = generateSeismicWave1(waveIndex);
			socket.emit('seismic_wave', {
				wave_sample: waveSample,
				sampling_rate: samplingRate,
				building_type: building_type // contains the natural frequency of the building in Hz
			});
			waveIndex++;
			if (waveIndex >= maxWaveformPoints) {
				clearInterval(sendWave);
			}
		}, 10); // 10 milliseconds = 0.01 seconds

		// Array to store markers with time and label
		let markers: { time: number; label: string }[] = [];

		// Listen for processed data from the server
		socket.on('seismic_update', function (data: any) {
			// content: result of ML/AI classification (prediction)
			if (data.message !== '') {
				content = data.message;
			}

			// Include P-wave, Inference, and S-wave indicator as vertical line if detected
			if (data.signal.sent) {
				markers = markers.concat({ time: waveIndex / samplingRate, label: data.signal.message }); // in seconds
			}
		});

		// Create a new P5 sketch
		new p5((p) => {
			let timeIncrement = 1 / 100; // Time increment for each data point (0.01 seconds, assuming 100 Hz sampling rate)
			let currentTime = 0; // Track the current time in seconds

			// Create the P5 sketch
			p.setup = () => {
				waveform.textContent = '';
				p.createCanvas(800, 200).parent(waveform);
			};

			// Draw the waveform
			p.draw = () => {
				p.background(220);

				// Draw the waveform
				p.noFill();
				p.stroke(0);
				p.beginShape();

				// Calculate the width per data point
				let pointsToShow = Math.min(data.length, maxDataPoints);
				let xIncrement = p.width / maxDataPoints; // 800 / 1000 = 0.8 px/data point

				for (let i = 0; i < pointsToShow; i++) {
					// Calculate x based on whether we are still filling or scrolling
					let x;
					if (data.length < maxDataPoints) {
						// If we haven't filled 10 seconds, fill from left to right
						x = i * xIncrement;
					} else {
						// If we have filled the buffer, start scrolling left
						x = (i - (data.length - maxDataPoints)) * xIncrement;
					}

					// Map the y value to the canvas height, clamping it to a max of 10
					const yValue = Math.min(data[i], 10); // Clamp y value to a max of 10
					const y = p.map(yValue, -10, 10, p.height, 0); // Map y to fit within the canvas

					p.vertex(x, y);
				}

				p.endShape();

				// Draw the y-axis labels
				p.textAlign(p.RIGHT, p.CENTER);
				for (let yValue = -10; yValue <= 10; yValue += 4) {
					let y = p.map(yValue, -10, 10, p.height, 0);
					p.fill(0); // Set fill color to black for the y-axis title
					p.text(`${yValue}`, 40, y);
					p.stroke(200);
					p.line(45, y, p.width, y);
				}

				// Draw y-axis title
				p.textAlign(p.CENTER, p.CENTER);
				p.fill(0); // Set fill color to black for the y-axis title
				p.push();
				p.translate(20, p.height / 2); // Position for the y-axis title
				p.rotate(-p.HALF_PI); // Rotate text to be vertical
				p.text('ground motion in m/s²', 0, 0);
				p.pop();

				// Draw markers (vertical lines and labels)
				markers.forEach((marker) => {
					let markerX = p.map(
						marker.time,
						currentTime * (100 / 60), // 100 Hz sampling rate, but P5 runs at 60 Hz. Hence we need to sync up the time
						(currentTime + maxDataPoints * timeIncrement) * (100 / 60), // 100 Hz sampling rate, but P5 runs at 60 Hz. Hence we need to sync up the time
						0,
						p.width
					);
					if (markerX >= 0 && markerX <= p.width) {
						// Draw the vertical line
						p.stroke(255, 0, 0); // Red line for marker
						p.line(markerX, 0, markerX, p.height);

						// Draw the label below the line
						p.textAlign(p.CENTER, p.TOP);
						p.fill(0);
						p.text(marker.label, markerX, p.height - 20);
					}
				});

				// Generate new data and update the array
				data.push(waveSample);

				// Update the current time if we have filled the maxDataPoints
				if (data.length > maxDataPoints) {
					data.shift(); // Remove the oldest sample
					currentTime += timeIncrement; // Increment the timeline time by the time increment
				}
			};
		});

		disabled = false;
	}
</script>

<svelte:head>
	<title>Earthquake Early Warning System</title>
</svelte:head>

<div class="mx-auto grid w-full max-w-2xl gap-2">
	<h1 class="text-2xl font-semibold">Earthquake Early Warning System</h1>
</div>

<div class="mx-auto grid w-full max-w-4xl items-start gap-6 md:grid-cols-1 lg:grid-cols-1">
	<div class="grid gap-6">
		<Card.Root>
			<Card.Header>
				<Card.Title>Earthquake Simulation and Warning System using Machine Learning</Card.Title>
				<Card.Description>
					Experience real-time earthquake simulations and structural response analysis through our
					web-based Earthquake Simulation and Warning System. Utilizing machine learning, it
					predicts the impact of seismic waves on structures, providing early insights and warnings.
				</Card.Description>
			</Card.Header>
			<Card.Content>
				<form class="flex flex-col gap-4">
					<Tabs.Root value="simulation" class="w-full">
						<Tabs.List class="grid w-full grid-cols-2">
							<Tabs.Trigger value="simulation">Earthquake Wave Simulation</Tabs.Trigger>
							<Tabs.Trigger value="about">About</Tabs.Trigger>
						</Tabs.List>
						<Tabs.Content value="simulation">
							<Card.Root>
								<Card.Header>
									<Card.Title>Earthquake Wave Simulation</Card.Title>
									<Card.Description
										>Simulate an earthquake and see how warning system works</Card.Description
									>
								</Card.Header>
								<Card.Content class="space-y-2">
									<div class="flex items-center justify-center space-y-1">
										<img
											class="mx-auto"
											src="/image740-5.png"
											alt="house-sensor-earthquake-ilustration"
										/>
									</div>
									<div id="message">{@html content}</div>
									<div class="space-y-1">
										<Label for="name">Wave</Label>
										<div
											style="min-height: 200px; border: 1px solid grey;"
											bind:this={waveform}
										></div>
									</div>
									<div class="space-y-1">
										<Label for="example">Select Earthquake</Label>
										<RadioGroup.Root bind:value={example}>
											<div class="flex items-center space-x-2">
												<RadioGroup.Item value="Example 1" id="example1" />
												<Label for="example1">Example 1 (Minor: ~ 2m/s2)</Label>
											</div>
											<div class="flex items-center space-x-2">
												<RadioGroup.Item value="Example 2" id="example2" />
												<Label for="example2">Example 2 (Moderate: ~ 6m/s2)</Label>
											</div>
											<div class="flex items-center space-x-2">
												<RadioGroup.Item value="Example 3" id="example3" />
												<Label for="example3">Example 3 (Major: ~ 10m/s2)</Label>
											</div>
										</RadioGroup.Root>
									</div>
									<div class="space-y-1">
										<Label for="example">Building Type</Label>
										<RadioGroup.Root bind:value={building_type}>
											<div class="flex items-center space-x-2">
												<!-- 3 Hz -->
												<RadioGroup.Item value="3" id="buildingtype1" />
												<Label for="buildingtype1">1 Floor House (36 m2)</Label>
											</div>
											<div class="flex items-center space-x-2">
												<!-- 1.5 Hz -->
												<RadioGroup.Item value="1.5" id="buildingtype2" />
												<Label for="buildingtype2">2 Floors House (72 m2)</Label>
											</div>
										</RadioGroup.Root>
									</div>
								</Card.Content>
								<Card.Footer>
									<div class="space-y-1">
										<Button on:click={analyseWave} {disabled}>
											{#if disabled}
												<Reload class="mr-2 h-4 w-4 animate-spin" />
											{/if}
											{buttonText}
										</Button>
										<br />
										<br />
										<div class="text-muted-foreground text-sm">
											Note: Please refresh to try another simulation! If the simulation is not
											working, please reload the page, since it might encounter a problem due to
											serverless computing environment.
										</div>
									</div>
								</Card.Footer>
							</Card.Root>
						</Tabs.Content>
						<Tabs.Content value="about">
							<Card.Root>
								<Card.Header>
									<Card.Title>Earthquake Early Warning System</Card.Title>
								</Card.Header>
								<Card.Content class="space-y-2">
									<Label for="name">Author</Label><br />
									<a href="https://dukenmarga.id">Duken Marga</a>
									<Separator class="my-4" />

									<Label for="name">Training Dataset</Label><br />
									<a href="https://github.com/smousavi05/STEAD">
										Mousavi, S. M., Sheng, Y., Zhu, W., Beroza G.C., (2019). STanford EArthquake
										Dataset (STEAD): A Global Data Set of Seismic Signals for AI, IEEE Access,
										doi:10.1109/ACCESS.2019.2947848
									</a>
									<Separator class="my-4" />

									<Label for="name">Tehcnical Note How It Works</Label><br />
									<div>
										The machine learing model will analyse the 3-seconds of earthquake P-wave and
										structural properties. P-wave is not damaging since it has low energy. The
										inference will predict the impact before the S-wave comes (more damaging than
										P-wave).
									</div>

									<Separator class="my-4" />

									<Label for="name">Icon</Label><br />
									<a href="https://www.flaticon.com/free-icons/3d-cube" title="3d cube icons">
										3d cube icons created by Freepik - Flaticon
									</a>
								</Card.Content>
							</Card.Root>
						</Tabs.Content>
					</Tabs.Root>
				</form>
			</Card.Content>
		</Card.Root>
	</div>
</div>
